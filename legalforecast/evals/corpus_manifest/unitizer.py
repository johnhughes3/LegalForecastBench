# pyright: reportPrivateUsage=false
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
import csv
import hashlib
import io
import json
import os
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from legalforecast._json_io import write_jsonl_objects
from legalforecast.contracts import (
    ARTIFACT_JSON_VALUE_V1,
    CYCLE1_MANIFEST_UNITIZER_SPEND_AUTHORITY_V1,
    CYCLE1_STAGE51_FINALIZED_UNITS_INTEGRATION_V1,
)
from legalforecast.evals.corpus_manifest.freeze import (
    VERDICT_ROLE_COMPATIBILITY,
)
from legalforecast.evals.corpus_manifest.stage51_r2 import (
    _file_commitment,
    _preflight_r2_outputs,
    _required_digest_argument,
    _required_path_argument,
    _verify_file_commitments,
    _write_jsonl_output,
    authenticate_stage51_r2_proposal,
)
from legalforecast.evals.corpus_manifest.stores import (
    CorpusStoreError,
    StoredDocument,
    VerdictRecord,
    index_document_store,
    index_verdict_payloads,
)
from legalforecast.evals.corpus_manifest.unitizer_publication import _write_stage_card
from legalforecast.evals.corpus_manifest.unitizer_replay import (
    _adopt_authenticated_unitization_replays,
    _verify_reconstructed_audits,
)
from legalforecast.evals.corpus_manifest.unitizer_shared import (
    _CYCLE1_FRESH_CANDIDATE_IDS,
    _FINALIZED_V1_AUTHORITY_MODE,
    _LABELING_MODEL_KEY,
    _LABELING_MODEL_REGISTRY_SHA256,
    _PROVIDER_CAPS_SHA256,
    _R2_AUTHORITY_MODE,
    _UNITS_SPEND_APPROVAL,
    AuthenticatedFinalizedOverlay,
    JsonRecord,
    ManifestUnitizerCommandError,
    ManifestUnitizerInputError,
    PreparedManifestUnitizerInputs,
    _command_required_string,
    _jsonl_records_from_bytes,
    _manifest_digest,
    _normalized_approval,
    _packet_replacement_units,
    _read_regular_input,
    _records_by_candidate,
    _validate_retained_record,
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
    LlmBatchResult,
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

_UNITS_SPEND_CAP_MICROUSD = 5_000_000


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
        "--stage51-authority-mode",
        choices=(_FINALIZED_V1_AUTHORITY_MODE, _R2_AUTHORITY_MODE),
        default=_FINALIZED_V1_AUTHORITY_MODE,
        help=(
            "Stage-51 authority contract. finalized-v1 preserves the historical "
            "same-candidate overlay; stage51-r2-proposal-v1 independently "
            "authenticates the owner-approved r2 proposal without changing v1."
        ),
    )
    parser.add_argument(
        "--finalized-units",
        type=Path,
        help="Authenticated Stage-51 finalized-units overlay JSONL.",
    )
    parser.add_argument(
        "--finalized-integration-manifest",
        type=Path,
        help="Manifest binding the finalized overlay to its owner-reviewed sources.",
    )
    parser.add_argument(
        "--expected-selection-sha256",
        required=True,
        help="Bare SHA-256 of the owner-corrected exact-100 selection.",
    )
    parser.add_argument(
        "--expected-finalized-units-sha256",
        help="Bare SHA-256 of the authenticated Stage-51 finalized overlay.",
    )
    parser.add_argument(
        "--expected-finalized-integration-manifest-sha256",
        help="Bare SHA-256 of the authenticated Stage-51 integration manifest.",
    )
    parser.add_argument(
        "--stage51-proposal-root",
        type=Path,
        help="r2 proposal directory used only with stage51-r2-proposal-v1.",
    )
    for option, label in (
        ("selection", "selection proposal"),
        ("overlay", "prediction-units overlay"),
        ("packet", "canonical owner packet"),
        ("validation", "validation report"),
        ("semantic-diff", "semantic diff"),
        ("inventory", "byte inventory"),
        ("checksums", "sha256s manifest"),
        ("integration-proposal", "integration proposal"),
    ):
        parser.add_argument(
            f"--expected-stage51-{option}-sha256",
            help=f"Bare SHA-256 of the r2 {label}.",
        )
    parser.add_argument(
        "--owner-approval-reference",
        required=True,
        help="Durable bead or record carrying the packet and spend approvals.",
    )
    parser.add_argument(
        "--owner-approval-source",
        type=Path,
        help=(
            "Hash-pinned durable approval observation (for example bd comments "
            "JSON). This is evidence behind the explicit owner checkpoint, not "
            "an identity authenticator."
        ),
    )
    parser.add_argument(
        "--expected-owner-approval-source-sha256",
        help="Bare SHA-256 of --owner-approval-source.",
    )
    parser.add_argument(
        "--fresh-five-selection",
        type=Path,
        help="Exact five-row selection used by the provider-free replay evidence.",
    )
    parser.add_argument("--expected-fresh-five-selection-sha256")
    parser.add_argument(
        "--fresh-five-units",
        type=Path,
        help="Exact five-row unitizer output independently reconstructed from journal.",
    )
    parser.add_argument("--expected-fresh-five-units-sha256")
    parser.add_argument("--fresh-five-audit", type=Path)
    parser.add_argument("--expected-fresh-five-audit-sha256")
    parser.add_argument("--fresh-five-run-card", type=Path)
    parser.add_argument("--expected-fresh-five-run-card-sha256")
    parser.add_argument("--fresh-five-review-queue", type=Path)
    parser.add_argument("--expected-fresh-five-review-queue-sha256")
    parser.add_argument("--fresh-five-terminal-review-queue", type=Path)
    parser.add_argument("--expected-fresh-five-terminal-review-queue-sha256")
    parser.add_argument(
        "--stage51-packet-approval",
        required=True,
        help="Verbatim Stage-51 packet approval naming the packet digest.",
    )
    parser.add_argument(
        "--units-spend-approval",
        required=True,
        help=(
            "Verbatim owner approval for the selected Stage-51 authority mode's "
            "USD 5 unitization ceiling."
        ),
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
    prepared = _prepare_manifest_unitizer_inputs_from_args(args)
    overlay = _authenticate_stage51_authority(args, prepared=prepared)
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
    immutable_publication = overlay.authority_mode == _R2_AUTHORITY_MODE
    authority_input_paths = (
        tuple(
            Path(str(commitment["path"]))
            for commitment in overlay.authority_input_commitments
        )
        if immutable_publication
        else (
            Path(args.finalized_units),
            Path(args.finalized_integration_manifest),
        )
    )
    input_paths = (
        selection_path,
        *(Path(path) for path in args.document_store_roots),
        *(Path(path) for path in args.verdict_sources),
        *authority_input_paths,
        model_registry_path,
        provider_caps_path,
        provider_journal_path,
    )
    if immutable_publication:
        _preflight_r2_outputs(
            args,
            output_root=output_root,
            input_paths=input_paths,
            primary_outputs=(
                prediction_units_path,
                audit_path,
                review_queue_path,
                terminal_queue_path,
            ),
        )
    replay_result = (
        _reconstruct_authenticated_fresh_replays(
            args,
            overlay=overlay,
            prepared=prepared,
            registry_entry=registry_entry,
            model_registry_sha256=model_registry_sha256,
            provider_caps=provider_caps,
            provider_caps_sha256=provider_caps_sha256,
            provider_journal_path=provider_journal_path,
        )
        if immutable_publication
        else None
    )
    if not bool(args.execute):
        if not immutable_publication:
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
                    "integration_manifest_sha256": (
                        overlay.integration_manifest_sha256
                    ),
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
        if immutable_publication:
            _recheck_r2_runtime_inputs(
                args,
                prepared=prepared,
                overlay=overlay,
                model_registry_sha256=model_registry_sha256,
                provider_caps_sha256=provider_caps_sha256,
            )
        _write_jsonl_output(
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
                    "reprocessed_candidate_count": len(overlay.reprocessed_records),
                    "reprocessed_candidate_ids": list(
                        overlay.reprocessed_candidate_ids
                    ),
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
            immutable=immutable_publication,
        )
        _write_jsonl_output(review_queue_path, [], immutable=immutable_publication)
        _write_jsonl_output(terminal_queue_path, [], immutable=immutable_publication)
        _write_stage_card(
            args,
            output_root=output_root,
            input_paths=input_paths,
            output_paths=(
                prediction_units_path,
                review_queue_path,
                terminal_queue_path,
            ),
            record_count=len(prepared.selection_records),
            paid=False,
            extra={
                "selection_sha256": prepared.selection_sha256,
                "retained_finalized_count": len(overlay.retained_records),
                "fresh_candidate_count": len(overlay.fresh_selection_records),
                "fresh_candidate_ids": list(overlay.fresh_candidate_ids),
                "reprocessed_candidate_count": len(overlay.reprocessed_records),
                "reprocessed_candidate_ids": list(overlay.reprocessed_candidate_ids),
                "finalized_overlay_sha256": overlay.overlay_sha256,
                "integration_manifest_sha256": overlay.integration_manifest_sha256,
                "owner_approval_reference": str(args.owner_approval_reference),
                "model_registry_sha256": model_registry_sha256,
                "model_key": registry_entry.registry_key,
                "provider_cycle_caps_sha256": provider_caps_sha256,
                "provider_journal": str(provider_journal_path),
                "verdict_source_sha256": list(prepared.verdict_source_sha256),
                "provider_execution": {
                    "provider_called": False,
                    "historical_replay_only": immutable_publication,
                    "authority_ordinals_created": False,
                    "new_paid_activity": False,
                },
            },
            dry_run=True,
            immutable=immutable_publication,
            authority_overlay=overlay,
            prepared=prepared,
            replay_audits=(
                replay_result.audit_records if replay_result is not None else ()
            ),
        )
        return

    terminal_paths = _validated_terminal_paths(args)
    expected_candidates = set(overlay.fresh_candidate_ids)
    terminal_escalations: dict[
        str, tuple[LlmStageAUnitizerTerminalEscalation, Mapping[str, Any]]
    ] = {}
    spend_authority_path: Path | None = None
    spend_authority_identity: str | None = None
    if immutable_publication:
        if replay_result is None:
            raise ManifestUnitizerCommandError(
                "Stage-51 r2 execution lacks its provider-free replay result"
            )
        result = replay_result
    else:
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
                    registry_entry.provider: provider_caps.cap_usd(
                        registry_entry.provider
                    )
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
    reprocessed_records = {
        str(record["candidate_id"]): dict(record)
        for record in overlay.reprocessed_records
    }
    merged_records = tuple(
        retained_records.get(candidate_id)
        or reprocessed_records.get(candidate_id)
        or fresh_records[candidate_id]
        for candidate_id in (
            str(record["candidate_id"]) for record in prepared.selection_records
        )
    )
    if immutable_publication:
        _validate_r2_final_composition(merged_records)
    retained_audits: tuple[JsonRecord, ...] = tuple(
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
    fresh_audits: dict[str, JsonRecord] = {
        str(record["candidate_id"]): dict(record) for record in result.audit_records
    }
    retained_audits_by_candidate: dict[str, JsonRecord] = {
        str(record["candidate_id"]): record for record in retained_audits
    }
    reprocessed_audits: tuple[JsonRecord, ...] = tuple(
        {
            "stage": "llm-unitize-manifest",
            "status": "reprocessed_finalized",
            "candidate_id": str(record["candidate_id"]),
            "case_id": str(record["case_id"]),
            "model_key": registry_entry.registry_key,
            "model_registry_sha256": model_registry_sha256,
            "provider_called": False,
            "provider_replay_adopted": False,
            "reprocessed_finalized": True,
            "finalized_overlay_sha256": overlay.overlay_sha256,
            "unit_count": len(cast(list[object], record["prediction_units"])),
            "scorable_unit_count": len(cast(list[object], record["prediction_units"])),
            "review_items": [],
            "unitization_review_queue": [],
            "input_tokens": 0,
            "output_tokens": 0,
            "estimated_cost": 0.0,
        }
        for record in overlay.reprocessed_records
    )
    reprocessed_audits_by_candidate: dict[str, JsonRecord] = {
        str(record["candidate_id"]): record for record in reprocessed_audits
    }
    merged_audits: tuple[JsonRecord, ...] = tuple(
        retained_audits_by_candidate.get(candidate_id)
        or reprocessed_audits_by_candidate.get(candidate_id)
        or fresh_audits[candidate_id]
        for candidate_id in (
            str(record["candidate_id"]) for record in prepared.selection_records
        )
    )
    if immutable_publication:
        _recheck_r2_runtime_inputs(
            args,
            prepared=prepared,
            overlay=overlay,
            model_registry_sha256=model_registry_sha256,
            provider_caps_sha256=provider_caps_sha256,
        )
    _write_jsonl_output(
        prediction_units_path, merged_records, immutable=immutable_publication
    )
    _write_jsonl_output(audit_path, merged_audits, immutable=immutable_publication)
    _write_jsonl_output(
        review_queue_path,
        unitization_review_queue_records(merged_audits),
        immutable=immutable_publication,
    )
    _write_jsonl_output(
        terminal_queue_path,
        result.terminal_review_queue_records,
        immutable=immutable_publication,
    )
    prediction_units_sha256 = hashlib.sha256(
        prediction_units_path.read_bytes()
    ).hexdigest()
    audit_sha256 = hashlib.sha256(audit_path.read_bytes()).hexdigest()
    stage_output_paths = (
        prediction_units_path,
        audit_path,
        review_queue_path,
        terminal_queue_path,
    )
    if not immutable_publication:
        if spend_authority_path is None or spend_authority_identity is None:
            raise ManifestUnitizerCommandError(
                "finalized-v1 execution lacks its provider spend authority"
            )
        stage_output_paths = (
            *stage_output_paths,
            provider_journal_path,
            spend_authority_path,
        )
    _write_stage_card(
        args,
        output_root=output_root,
        input_paths=(
            *input_paths,
            *terminal_paths,
        ),
        output_paths=stage_output_paths,
        record_count=len(merged_records),
        paid=not immutable_publication,
        extra={
            "manifest_mode": True,
            "selection_sha256": prepared.selection_sha256,
            "selection_count": len(prepared.selection_records),
            "retained_finalized_count": len(overlay.retained_records),
            "fresh_candidate_count": len(overlay.fresh_selection_records),
            "fresh_candidate_ids": list(overlay.fresh_candidate_ids),
            **(
                {
                    "reprocessed_candidate_count": len(overlay.reprocessed_records),
                    "reprocessed_candidate_ids": list(
                        overlay.reprocessed_candidate_ids
                    ),
                }
                if immutable_publication
                else {}
            ),
            "finalized_overlay_sha256": overlay.overlay_sha256,
            "integration_manifest_sha256": overlay.integration_manifest_sha256,
            "owner_approval_reference": str(args.owner_approval_reference),
            "stage51_packet_approval": str(args.stage51_packet_approval),
            "units_spend_approval": str(args.units_spend_approval),
            "prediction_units_sha256": prediction_units_sha256,
            "audit_sha256": audit_sha256,
            **(
                {
                    "provider_spend_authority": str(spend_authority_path),
                    "provider_spend_authority_identity_sha256": (
                        spend_authority_identity
                    ),
                }
                if not immutable_publication
                else {}
            ),
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
            **(
                {
                    "provider_execution": {
                        "provider_called": False,
                        "historical_replay_only": True,
                        "authority_ordinals_created": False,
                        "new_paid_activity": False,
                    }
                }
                if immutable_publication
                else {}
            ),
            "terminal_escalation_count": len(terminal_escalations),
        },
        dry_run=False,
        immutable=immutable_publication,
        authority_overlay=overlay,
        prepared=prepared,
        replay_audits=result.audit_records,
    )


def _validate_r2_final_composition(records: Sequence[JsonRecord]) -> None:
    final_unit_count = sum(
        len(cast(list[object], record["prediction_units"])) for record in records
    )
    final_scorable_count = sum(
        prediction_unit_from_record(raw_unit).should_score
        for record in records
        for raw_unit in cast(list[object], record["prediction_units"])
    )
    if final_unit_count != 425 or final_scorable_count != 425:
        raise ManifestUnitizerCommandError(
            "Stage-51 r2 final composition must contain exactly 425 scorable units"
        )


def _validated_terminal_paths(args: argparse.Namespace) -> tuple[Path, ...]:
    if bool(args.continue_on_error):
        raise ManifestUnitizerCommandError(
            "manifest-mode paid execution refuses --continue-on-error"
        )
    terminal_paths = tuple(Path(path) for path in (args.terminal_escalation or ()))
    if terminal_paths:
        mode = str(
            getattr(args, "stage51_authority_mode", _FINALIZED_V1_AUTHORITY_MODE)
        )
        message = (
            "manifest replay execution does not admit terminal escalation receipts"
            if mode == _R2_AUTHORITY_MODE
            else "exact six-case execution does not admit terminal escalation receipts"
        )
        raise ManifestUnitizerCommandError(message)
    return terminal_paths


def _prepare_manifest_unitizer_inputs_from_args(
    args: argparse.Namespace,
) -> PreparedManifestUnitizerInputs:
    return prepare_manifest_unitizer_inputs(
        selection_path=Path(args.selection),
        document_store_roots=tuple(Path(path) for path in args.document_store_roots),
        verdict_sources=tuple(Path(path) for path in args.verdict_sources),
        expected_verdict_source_sha256=tuple(
            str(value) for value in args.expected_verdict_source_sha256
        ),
        target_case_count=int(args.target_case_count),
    )


def _reconstruct_authenticated_fresh_replays(
    args: argparse.Namespace,
    *,
    overlay: AuthenticatedFinalizedOverlay,
    prepared: PreparedManifestUnitizerInputs,
    registry_entry: ModelRegistryEntry,
    model_registry_sha256: str,
    provider_caps: ProviderCycleCaps,
    provider_caps_sha256: str,
    provider_journal_path: Path,
) -> LlmBatchResult:
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
    result = _adopt_authenticated_unitization_replays(
        selection_records=overlay.fresh_selection_records,
        parser_records=fresh_parser_records,
        markdown_root=prepared.markdown_root,
        markdown_bytes=fresh_markdown_bytes,
        registry_entry=registry_entry,
        model_registry_sha256=model_registry_sha256,
        provider_journal_path=provider_journal_path,
        provider_cycle_id=provider_caps.cycle_id,
        provider_cycle_caps_sha256=provider_caps_sha256,
        provider_account=_provider_account(provider_caps, registry_entry.provider),
        provider_attempt_namespace=args.provider_attempt_namespace,
    )
    if (
        overlay.expected_fresh_records
        and result.records != overlay.expected_fresh_records
    ):
        raise ManifestUnitizerCommandError(
            "provider-free reconstruction differs from the pinned fresh-five units"
        )
    if overlay.expected_fresh_audits:
        _verify_reconstructed_audits(
            result.audit_records, expected=overlay.expected_fresh_audits
        )
    return result


def _recheck_r2_runtime_inputs(
    args: argparse.Namespace,
    *,
    prepared: PreparedManifestUnitizerInputs,
    overlay: AuthenticatedFinalizedOverlay,
    model_registry_sha256: str,
    provider_caps_sha256: str,
) -> None:
    if _prepare_manifest_unitizer_inputs_from_args(args) != prepared:
        raise ManifestUnitizerCommandError(
            "Stage-51 r2 manifest inputs changed before publication"
        )
    if (
        hashlib.sha256(
            _read_regular_input(Path(args.model_registry), "model registry")
        ).hexdigest()
        != model_registry_sha256
    ):
        raise ManifestUnitizerCommandError(
            "Stage-51 r2 model registry changed before publication"
        )
    if (
        hashlib.sha256(
            _read_regular_input(Path(args.provider_cycle_caps), "provider cycle caps")
        ).hexdigest()
        != provider_caps_sha256
    ):
        raise ManifestUnitizerCommandError(
            "Stage-51 r2 provider cycle caps changed before publication"
        )
    _verify_file_commitments(overlay.authority_input_commitments)


def _output_path(args: argparse.Namespace, name: str, default: Path) -> Path:
    value = getattr(args, name, None)
    return Path(value) if value is not None else default


def _authenticate_stage51_authority(
    args: argparse.Namespace,
    *,
    prepared: PreparedManifestUnitizerInputs,
) -> AuthenticatedFinalizedOverlay:
    mode = str(getattr(args, "stage51_authority_mode", _FINALIZED_V1_AUTHORITY_MODE))
    if mode == _FINALIZED_V1_AUTHORITY_MODE:
        finalized_units = _required_path_argument(args, "finalized_units")
        integration_manifest = _required_path_argument(
            args, "finalized_integration_manifest"
        )
        expected_overlay = _required_digest_argument(
            args, "expected_finalized_units_sha256"
        )
        expected_manifest = _required_digest_argument(
            args, "expected_finalized_integration_manifest_sha256"
        )
        authenticated = authenticate_finalized_overlay(
            finalized_units_path=finalized_units,
            integration_manifest_path=integration_manifest,
            prepared=prepared,
            expected_selection_sha256=str(args.expected_selection_sha256),
            expected_overlay_sha256=expected_overlay,
            expected_integration_manifest_sha256=expected_manifest,
            owner_approval_reference=str(args.owner_approval_reference),
            stage51_packet_approval=str(args.stage51_packet_approval),
            units_spend_approval=str(args.units_spend_approval),
        )
        return AuthenticatedFinalizedOverlay(
            retained_records=authenticated.retained_records,
            fresh_selection_records=authenticated.fresh_selection_records,
            overlay_sha256=authenticated.overlay_sha256,
            integration_manifest_sha256=authenticated.integration_manifest_sha256,
            fresh_candidate_ids=authenticated.fresh_candidate_ids,
            reprocessed_records=authenticated.reprocessed_records,
            reprocessed_candidate_ids=authenticated.reprocessed_candidate_ids,
            authority_input_commitments=(
                _file_commitment(finalized_units, "finalized_units"),
                _file_commitment(integration_manifest, "integration_manifest"),
            ),
        )
    if mode != _R2_AUTHORITY_MODE:
        raise ManifestUnitizerCommandError(
            f"unsupported Stage-51 authority mode: {mode}"
        )
    if bool(args.resume):
        raise ManifestUnitizerCommandError(
            "Stage-51 r2 authority publication requires --no-resume"
        )
    return authenticate_stage51_r2_proposal(args, prepared=prepared)


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
    if manifest.get("artifact") != str(CYCLE1_STAGE51_FINALIZED_UNITS_INTEGRATION_V1):
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
    integration_sources = _verify_integration_sources(manifest)
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
        try:
            scorable_unit_count += sum(
                prediction_unit_from_record(unit).should_score for unit in units
            )
        except (TypeError, ValueError) as exc:
            raise ManifestUnitizerCommandError(
                f"{candidate_id}: finalized prediction unit is invalid: {exc}"
            ) from exc
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
    _verify_finalized_overlay_derivation(
        manifest,
        overlay_by_candidate=overlay_by_candidate,
        integration_sources=integration_sources,
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


def _verify_integration_sources(manifest: Mapping[str, Any]) -> dict[str, bytes]:
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
    payloads: dict[str, bytes] = {}
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
        payloads[path_field] = payload
    return payloads


def _verify_finalized_overlay_derivation(
    manifest: Mapping[str, Any],
    *,
    overlay_by_candidate: Mapping[str, JsonRecord],
    integration_sources: Mapping[str, bytes],
) -> None:
    base_records = _jsonl_records_from_bytes(
        integration_sources["base_prediction_units"],
        label="base prediction units",
        error_factory=ManifestUnitizerCommandError,
    )
    base_by_candidate = _records_by_candidate(
        base_records, label="base prediction units"
    )
    if set(base_by_candidate) != set(overlay_by_candidate):
        raise ManifestUnitizerCommandError(
            "finalized overlay candidate set differs from the authenticated base"
        )

    replaced_value_raw = manifest.get("replaced_candidates")
    if not isinstance(replaced_value_raw, Mapping) or not replaced_value_raw:
        raise ManifestUnitizerCommandError(
            "integration manifest lacks replaced candidate counts"
        )
    replaced_value = cast(Mapping[object, object], replaced_value_raw)
    replaced_counts: dict[str, int] = {}
    for candidate_id, raw_count in replaced_value.items():
        if type(raw_count) is not int or raw_count <= 0:
            raise ManifestUnitizerCommandError(
                "integration manifest has an invalid replaced candidate count"
            )
        replaced_counts[str(candidate_id)] = raw_count

    sole_fields = [
        str(field)
        for field in manifest
        if str(field).endswith("_finalized_unit_sha256")
    ]
    if len(sole_fields) != 1:
        raise ManifestUnitizerCommandError(
            "integration manifest must bind one sole finalized unit"
        )
    sole_candidate_id = sole_fields[0].removesuffix("_finalized_unit_sha256")

    packet_units = _packet_replacement_units(integration_sources["packet"])
    packet_candidate_ids = set(packet_units)
    if packet_candidate_ids | {sole_candidate_id} != set(replaced_counts):
        raise ManifestUnitizerCommandError(
            "integration replacement sources do not cover the replaced candidates"
        )

    expected_packet_hashes = {
        str(unit["unit_id"]): hashlib.sha256(
            ARTIFACT_JSON_VALUE_V1.encode(dict(unit))
        ).hexdigest()
        for units in packet_units.values()
        for unit in units
    }
    if manifest.get("packet_unit_sha256") != expected_packet_hashes:
        raise ManifestUnitizerCommandError(
            "integration manifest packet commitments differ from the approved packet"
        )

    worksheet_field = next(
        field
        for field in integration_sources
        if field.startswith("worksheet_") and field.endswith("_source")
    )
    sole_units = _worksheet_finalized_units(
        integration_sources[worksheet_field], candidate_id=sole_candidate_id
    )
    replacements = {**packet_units, sole_candidate_id: sole_units}
    for candidate_id, expected_count in replaced_counts.items():
        replacement_units = replacements[candidate_id]
        if len(replacement_units) != expected_count:
            raise ManifestUnitizerCommandError(
                f"{candidate_id}: replacement unit count differs from the manifest"
            )

    for candidate_id, base_record in base_by_candidate.items():
        expected_record = dict(base_record)
        if candidate_id in replacements:
            expected_record["prediction_units"] = replacements[candidate_id]
        if overlay_by_candidate[candidate_id] != expected_record:
            raise ManifestUnitizerCommandError(
                f"{candidate_id}: finalized overlay is not derived from the "
                "authenticated base and approved replacement sources"
            )


def _worksheet_finalized_units(
    payload: bytes, *, candidate_id: str
) -> list[JsonRecord]:
    try:
        text = payload.decode("utf-8")
        rows = list(csv.DictReader(io.StringIO(text), delimiter="\t"))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ManifestUnitizerCommandError(
            "finalized worksheet cannot be parsed"
        ) from exc
    matches = [
        row
        for row in rows
        if row.get("candidate_id") == candidate_id
        and row.get("decision_status") == "final"
    ]
    if len(matches) != 1:
        raise ManifestUnitizerCommandError(
            "finalized worksheet must contain one final sole-unit row"
        )
    try:
        raw_units = json.loads(matches[0]["finalized_units_json"])
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ManifestUnitizerCommandError(
            "finalized worksheet sole-unit JSON is invalid"
        ) from exc
    if not isinstance(raw_units, list) or not raw_units:
        raise ManifestUnitizerCommandError(
            "finalized worksheet sole-unit JSON must be a nonempty list"
        )
    units: list[JsonRecord] = []
    for raw_unit in cast(list[object], raw_units):
        if not isinstance(raw_unit, Mapping):
            raise ManifestUnitizerCommandError(
                "finalized worksheet contains an invalid prediction unit"
            )
        unit = dict(cast(Mapping[str, Any], raw_unit))
        prediction_unit_from_record(unit)
        units.append(unit)
    return units


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
        if (
            unit is None
            or digest
            != hashlib.sha256(ARTIFACT_JSON_VALUE_V1.encode(dict(unit))).hexdigest()
        ):
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
    if (
        len(sole_units) != 1
        or hashlib.sha256(
            ARTIFACT_JSON_VALUE_V1.encode(dict(sole_units[0]))
        ).hexdigest()
        != sole_digest
    ):
        raise ManifestUnitizerCommandError(
            "integration manifest sole-unit commitment changed"
        )


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
        "artifact": str(CYCLE1_MANIFEST_UNITIZER_SPEND_AUTHORITY_V1),
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
    canonical = ARTIFACT_JSON_VALUE_V1.encode(payload)
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


# contract-ratchet: allow byte digest for the existing terminal receipt sidecar
def _sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _provider_account(provider_caps: ProviderCycleCaps, provider: str) -> str:
    """Use the journal's legacy default account when caps predate aliases."""

    cap = provider_caps.providers.get(provider)
    if cap is None:
        raise ManifestUnitizerCommandError(
            f"provider cycle caps has no entry for {provider!r}"
        )
    return cap.account or "default"


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
