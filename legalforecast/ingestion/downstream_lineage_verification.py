# pyright: reportPrivateUsage=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportUnknownParameterType=false

"""Importable materialized downstream-lineage verification helpers."""

from __future__ import annotations

import argparse
import os
import sqlite3
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast, overload


def _cli() -> Any:
    from legalforecast import cli as cli_module

    return cli_module


@dataclass(frozen=True, slots=True)
class VerifiedMaterializedDownstreamLineage:
    paths: tuple[Path, ...]
    artifact_bytes: Mapping[str, bytes]
    manifest_records: tuple[Mapping[str, Any], ...]
    clearance_records: tuple[Mapping[str, Any], ...]
    selection_records: tuple[Mapping[str, Any], ...]
    resolved_records: tuple[Mapping[str, Any], ...]
    document_tree: Mapping[str, bytes]
    absent_artifact_paths: tuple[str, ...] = ()
    resolved_lineage_selection_records: tuple[Mapping[str, Any], ...] | None = None
    recovered_public_capability: object | None = None
    consolidated_recovery_capability: object | None = None
    fresh_ledger_namespace: Path | None = None
    docket_decision_authority: object | None = None
    verified_successor_selection_card: object | None = None
    authenticated_paths: tuple[Path, ...] = ()

    def __len__(self) -> int:
        return len(self.paths)

    @overload
    def __getitem__(self, index: int) -> Path: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[Path, ...]: ...

    def __getitem__(self, index: int | slice) -> Path | tuple[Path, ...]:
        return self.paths[index]

    def __iter__(self) -> Iterator[Path]:
        return iter(self.paths)


def authenticated_path_aliases(paths: Sequence[Path]) -> tuple[Path, ...]:
    """Keep absolute authenticated path spellings without resolving aliases."""

    return tuple(Path(os.path.abspath(path)) for path in paths)


def downstream_docket_decision_descriptor(
    verified: object,
) -> object | None:
    """Return authority metadata from a replay-verified downstream lineage."""

    _cli_ns = _cli()
    CommandError = _cli_ns.CommandError
    if verified is None:
        return None
    if isinstance(verified, VerifiedMaterializedDownstreamLineage):
        return verified.docket_decision_authority
    raise CommandError("materialization downstream lineage has an invalid type")


def require_materialized_downstream_lineage_unchanged(
    verified: VerifiedMaterializedDownstreamLineage,
    *,
    document_root: Path,
) -> None:
    """Recheck captured bytes without replaying materialization authority."""

    _cli_ns = _cli()
    CommandError = _cli_ns.CommandError
    PurchaseApprovalError = _cli_ns.PurchaseApprovalError
    _materializer_tree_snapshot = _cli_ns._materializer_tree_snapshot
    _replay_materialized_docket_decision_authority = (
        _cli_ns._replay_materialized_docket_decision_authority
    )
    _require_snapshot_unchanged = _cli_ns._require_snapshot_unchanged
    require_fresh_purchase_ledger_namespace = (
        _cli_ns.require_fresh_purchase_ledger_namespace
    )
    _require_snapshot_unchanged(
        {
            Path(raw_path): payload
            for raw_path, payload in verified.artifact_bytes.items()
        },
        label="materialization downstream lineage artifact",
    )
    if _materializer_tree_snapshot(document_root) != verified.document_tree:
        raise CommandError("materialization document tree changed during execution")
    if verified.fresh_ledger_namespace is not None:
        try:
            require_fresh_purchase_ledger_namespace(verified.fresh_ledger_namespace)
        except (OSError, PurchaseApprovalError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
    if verified.docket_decision_authority is not None:
        _replay_materialized_docket_decision_authority(
            verified.docket_decision_authority
        )


def verify_materialized_downstream_lineage(
    *,
    run_card_path: Path,
    manifest_path: Path,
    clearance_path: Path,
    document_root: Path,
    selection_path: Path | None = None,
    controlled_private_root: Path | None = None,
    initialization_receipt_path: Path | None = None,
) -> VerifiedMaterializedDownstreamLineage:
    _cli_ns = _cli()
    CaseDevPurchaseJournal = _cli_ns.CaseDevPurchaseJournal
    CaseDevPurchaseLedgerError = _cli_ns.CaseDevPurchaseLedgerError
    CaseDevPurchasePolicyError = _cli_ns.CaseDevPurchasePolicyError
    CohortDocumentMaterializationError = _cli_ns.CohortDocumentMaterializationError
    CommandError = _cli_ns.CommandError
    DocumentSource = _cli_ns.DocumentSource
    FreeOnlyMaterializationInputs = _cli_ns.FreeOnlyMaterializationInputs
    ResolvedPostRecoveryError = _cli_ns.ResolvedPostRecoveryError
    _MaterializerDocketDecisionAuthority = _cli_ns._MaterializerDocketDecisionAuthority
    _build_materializer_derivations = _cli_ns._build_materializer_derivations
    _bytes_sha256 = _cli_ns._bytes_sha256
    _canonical_json_sha256 = _cli_ns._canonical_json_sha256
    _file_commitment_from_bytes = _cli_ns._file_commitment_from_bytes
    _materializer_clearance_lineage_kwargs = (
        _cli_ns._materializer_clearance_lineage_kwargs
    )
    _materializer_complete_selected_document_keys = (
        _cli_ns._materializer_complete_selected_document_keys
    )
    _materializer_consolidated_target_inputs = (
        _cli_ns._materializer_consolidated_target_inputs
    )
    _materializer_record_key = _cli_ns._materializer_record_key
    _materializer_recovery_source_commitments = (
        _cli_ns._materializer_recovery_source_commitments
    )
    _materializer_successor_v2_free_sources = (
        _cli_ns._materializer_successor_v2_free_sources
    )
    _materializer_tree_snapshot = _cli_ns._materializer_tree_snapshot
    _merge_verified_artifact_bytes = _cli_ns._merge_verified_artifact_bytes
    _prepare_free_only_cohort_documents = _cli_ns._prepare_free_only_cohort_documents
    _projection_json_bytes = _cli_ns._projection_json_bytes
    _projection_json_object = _cli_ns._projection_json_object
    _projection_jsonl_bytes = _cli_ns._projection_jsonl_bytes
    _projection_jsonl_records = _cli_ns._projection_jsonl_records
    _read_records = _cli_ns._read_records
    _read_singly_linked_regular_input = _cli_ns._read_singly_linked_regular_input
    _replacement_consolidation_selection_keys = (
        _cli_ns._replacement_consolidation_selection_keys
    )
    _require_materializer_artifact = _cli_ns._require_materializer_artifact
    _require_resolved_operation_bindings_dispatch = (
        _cli_ns._require_resolved_operation_bindings_dispatch
    )
    _require_resolved_post_recovery_dispatch = (
        _cli_ns._require_resolved_post_recovery_dispatch
    )
    _require_snapshot_unchanged = _cli_ns._require_snapshot_unchanged
    _required_str = _cli_ns._required_str
    _select_materializer_projection_after_recovery = (
        _cli_ns._select_materializer_projection_after_recovery
    )
    _selection_requires_resolved_post_recovery = (
        _cli_ns._selection_requires_resolved_post_recovery
    )
    _verified_successor_selection_card_from_projection = (
        _cli_ns._verified_successor_selection_card_from_projection
    )
    _verify_completed_preparation_for_frontier = (
        _cli_ns._verify_completed_preparation_for_frontier
    )
    _verify_materializer_clearance_lineage = (
        _cli_ns._verify_materializer_clearance_lineage
    )
    _verify_materializer_docket_decision_authority = (
        _cli_ns._verify_materializer_docket_decision_authority
    )
    _verify_materializer_projection = _cli_ns._verify_materializer_projection
    _verify_materializer_purchase_operations = (
        _cli_ns._verify_materializer_purchase_operations
    )
    _verify_materializer_recovery = _cli_ns._verify_materializer_recovery
    _verify_materializer_recovery_clearance_binding = (
        _cli_ns._verify_materializer_recovery_clearance_binding
    )
    _verify_materializer_resume = _cli_ns._verify_materializer_resume
    prepare_cohort_document_materialization = (
        _cli_ns.prepare_cohort_document_materialization
    )
    read_case_dev_purchase_authority_audit = (
        _cli_ns.read_case_dev_purchase_authority_audit
    )
    read_unique_regular_file = _cli_ns.read_unique_regular_file
    require_approved_case_dev_purchase_policy = (
        _cli_ns.require_approved_case_dev_purchase_policy
    )
    verified_docket_decision_document_keys = (
        _cli_ns.verified_docket_decision_document_keys
    )
    verify_case_dev_purchase_policy = _cli_ns.verify_case_dev_purchase_policy
    verify_case_dev_purchase_policy_cohort_binding = (
        _cli_ns.verify_case_dev_purchase_policy_cohort_binding
    )
    run_card_bytes = _require_materializer_artifact(
        run_card_path, label="materialization lineage run card"
    )
    card = _projection_json_object(run_card_bytes, source=run_card_path)
    if (
        card.get("schema_version")
        # contract-ratchet: allow moved CLI replay still matches the frozen run-card id.
        != "legalforecast.acquisition_run_card.v1"
        or card.get("stage") != "materialize-cohort-documents"
        or card.get("status") != "completed"
        or card.get("dry_run") is not False
        or card.get("execute") is not True
        or card.get("paid_activity_requested") is not False
        or card.get("paid_activity_executed") is not False
        or card.get("source_roots_mutated") is not False
        or card.get("zero_provider_activity_evidence") is not True
    ):
        raise CommandError("invalid completed materialization lineage run card")
    raw_inputs = card.get("input_paths")
    if not isinstance(raw_inputs, Sequence) or isinstance(raw_inputs, (str, bytes)):
        raise CommandError("materialization run card lacks exact input paths")
    input_paths = tuple(Path(str(path)) for path in cast(Sequence[object], raw_inputs))
    authority_mode = card.get("authority_mode")
    if "authority_mode" in card and not isinstance(authority_mode, str):
        raise CommandError("invalid materialization authority mode")
    if authority_mode == "free_only":
        if len(input_paths) != 11:
            raise CommandError("materialization run card input paths differ")
        if controlled_private_root is None:
            raise CommandError(
                "free-only materialization lineage requires a controlled private root"
            )
        if initialization_receipt_path is not None:
            raise CommandError(
                "free-only materialization rejects a ledger initialization receipt"
            )
        raw_outputs = card.get("output_paths")
        if not isinstance(raw_outputs, Sequence) or isinstance(
            raw_outputs, (str, bytes)
        ):
            raise CommandError("materialization run card lacks exact output paths")
        output_paths = tuple(
            Path(str(path)) for path in cast(Sequence[object], raw_outputs)
        )
        if len(output_paths) != 6:
            raise CommandError("materialization run card output paths differ")
        materialized_root = output_paths[0].parent
        (
            preparation_root,
            preparation_summary_path,
            preparation_config_path,
            snapshot_manifest_path,
            target_root,
            free_clearance_path,
            cohort_policy_path,
            approval_checkpoint_path,
            approval_run_card_path,
            fee_schedule_path,
            ledger_path,
        ) = input_paths
        replay_args = argparse.Namespace(
            output_root=materialized_root,
            preparation_root=preparation_root,
            preparation_summary=preparation_summary_path,
            preparation_config=preparation_config_path,
            snapshot_manifest=snapshot_manifest_path,
            target_cohort_root=target_root,
            free_disclosure_clearance=free_clearance_path,
            cohort_policy=cohort_policy_path,
            controlled_private_root=controlled_private_root,
            run_card_output=run_card_path,
            log_output=None,
        )
        publication = _prepare_free_only_cohort_documents(
            replay_args,
            FreeOnlyMaterializationInputs(
                checkpoint_path=approval_checkpoint_path,
                run_card_path=approval_run_card_path,
                fee_schedule_path=fee_schedule_path,
                canonical_ledger_path=ledger_path.resolve(),
            ),
        )
        expected_outputs = (
            manifest_path,
            clearance_path,
            publication.restriction_path,
            publication.derivations_path,
            publication.summary_path,
            document_root,
        )
        if tuple(path.resolve() for path in output_paths) != tuple(
            path.resolve() for path in expected_outputs
        ):
            raise CommandError(
                "materialization lineage outputs differ from parser inputs"
            )
        output_snapshots = {
            path: _read_singly_linked_regular_input(
                path, label="materialization lineage output"
            )
            for path in expected_outputs[:-1]
        }
        document_tree_snapshot = _materializer_tree_snapshot(document_root)
        document_commitments = {
            document.destination.relative_to(document_root).as_posix(): (
                "sha256:" + _required_str(document.manifest_record, "sha256")
            )
            for document in publication.materialization.documents
        }
        verified_document_commitments = {
            relative_path: _bytes_sha256(payload)
            for relative_path, payload in document_tree_snapshot.items()
        }
        if verified_document_commitments != document_commitments:
            raise CommandError("materialization document-tree commitment changed")
        summary_bytes = _projection_json_bytes(
            {
                **publication.materialization.summary,
                "authority_mode": "free_only",
                "target_case_count": publication.target_case_count,
                "source_commitments": publication.source_commitments,
                "output_commitments": {
                    "document-downloads-merged.jsonl": _bytes_sha256(
                        publication.manifest_bytes
                    ),
                    "disclosure-clearance.jsonl": _bytes_sha256(
                        publication.clearance_bytes
                    ),
                    "restriction-evidence.jsonl": _bytes_sha256(
                        publication.restriction_bytes
                    ),
                    "materialization-derivations.jsonl": _bytes_sha256(
                        publication.derivations_bytes
                    ),
                    "documents": document_commitments,
                },
                "next_stage": "plan-parse-documents",
            }
        )
        output_commitments: dict[str, object] = {
            "document_manifest": _file_commitment_from_bytes(
                manifest_path, publication.manifest_bytes
            ),
            "disclosure_clearance": _file_commitment_from_bytes(
                clearance_path, publication.clearance_bytes
            ),
            "restriction_evidence": _file_commitment_from_bytes(
                publication.restriction_path, publication.restriction_bytes
            ),
            "materialization_derivations": _file_commitment_from_bytes(
                publication.derivations_path, publication.derivations_bytes
            ),
            "materialization_summary": {
                "path": str(publication.summary_path.resolve()),
                "sha256": _bytes_sha256(summary_bytes),
            },
            "document_tree": document_commitments,
        }
        if publication.authority_recheck is not None:
            publication.authority_recheck()
        _verify_materializer_resume(
            run_card_path=run_card_path,
            input_paths=publication.input_paths,
            manifest_path=manifest_path,
            manifest_bytes=publication.manifest_bytes,
            clearance_path=clearance_path,
            clearance_bytes=publication.clearance_bytes,
            restriction_path=publication.restriction_path,
            restriction_bytes=publication.restriction_bytes,
            derivations_path=publication.derivations_path,
            derivations_bytes=publication.derivations_bytes,
            summary_path=publication.summary_path,
            summary_bytes=summary_bytes,
            document_root=document_root,
            materialization=publication.materialization,
            source_commitments=publication.source_commitments,
            output_commitments=output_commitments,
            dry_run=False,
            authority_mode="free_only",
        )
        selection_records = tuple(
            _read_records(target_root / "target-cohort-selection.jsonl")
        )
        if selection_path is not None and (
            selection_path.resolve()
            != (target_root / "target-cohort-selection.jsonl").resolve()
            or read_unique_regular_file(selection_path)
            != read_unique_regular_file(target_root / "target-cohort-selection.jsonl")
        ):
            raise CommandError(
                "downstream selection differs from materialized target cohort"
            )
        captured_paths = {
            run_card_path: run_card_bytes,
            **dict(publication.captured_source_snapshots),
            **output_snapshots,
            **{
                document_root / relative_path: payload
                for relative_path, payload in document_tree_snapshot.items()
            },
        }
        _require_snapshot_unchanged(
            captured_paths,
            label="materialization downstream lineage artifact",
        )
        captured = {
            os.path.abspath(path): payload for path, payload in captured_paths.items()
        }
        return VerifiedMaterializedDownstreamLineage(
            paths=(
                run_card_path,
                publication.restriction_path,
                publication.derivations_path,
            ),
            artifact_bytes=captured,
            manifest_records=tuple(
                _projection_jsonl_records(
                    output_snapshots[manifest_path], source=manifest_path
                )
            ),
            clearance_records=tuple(
                _projection_jsonl_records(
                    output_snapshots[clearance_path], source=clearance_path
                )
            ),
            selection_records=selection_records,
            resolved_lineage_selection_records=selection_records,
            resolved_records=(),
            document_tree=document_tree_snapshot,
            fresh_ledger_namespace=ledger_path.resolve(),
            verified_successor_selection_card=(
                publication.verified_successor_selection_card
            ),
            authenticated_paths=authenticated_path_aliases(input_paths),
        )
    if authority_mode is not None:
        raise CommandError("unsupported materialization authority mode")
    if len(input_paths) not in {12, 13, 14, 15}:
        raise CommandError("materialization run card input paths differ")
    (
        preparation_root,
        preparation_summary_path,
        preparation_config_path,
        snapshot_manifest_path,
        target_root,
        free_clearance_path,
        recovery_root,
        purchased_clearance_path,
        purchased_clearance_card_path,
        purchase_policy_path,
        cohort_policy_path,
        ledger_path,
        *optional_inputs,
    ) = input_paths
    purchase_result_path: Path | None = None
    purchase_run_card_path: Path | None = None
    if len(input_paths) in {14, 15}:
        purchase_result_path, purchase_run_card_path, *optional_inputs = optional_inputs
    resolved_path = optional_inputs[0] if optional_inputs else None
    raw_outputs = card.get("output_paths")
    if not isinstance(raw_outputs, Sequence) or isinstance(raw_outputs, (str, bytes)):
        raise CommandError("materialization run card lacks exact output paths")
    output_paths = tuple(
        Path(str(path)) for path in cast(Sequence[object], raw_outputs)
    )
    if len(output_paths) != 6:
        raise CommandError("materialization run card output paths differ")
    materialized_root = output_paths[0].parent
    restriction_path = materialized_root / "restriction-evidence.jsonl"
    derivations_path = materialized_root / "materialization-derivations.jsonl"
    summary_path = materialized_root / "cohort-document-materialization.json"
    expected_outputs = (
        manifest_path,
        clearance_path,
        restriction_path,
        derivations_path,
        summary_path,
        document_root,
    )
    if tuple(path.resolve() for path in output_paths) != tuple(
        path.resolve() for path in expected_outputs
    ):
        raise CommandError("materialization lineage outputs differ from parser inputs")
    direct_input_paths = (
        preparation_summary_path,
        preparation_config_path,
        snapshot_manifest_path,
        free_clearance_path,
        purchased_clearance_path,
        purchased_clearance_card_path,
        purchase_policy_path,
        cohort_policy_path,
        ledger_path,
        *(
            (purchase_result_path, purchase_run_card_path)
            if purchase_result_path is not None and purchase_run_card_path is not None
            else ()
        ),
        *((resolved_path,) if resolved_path is not None else ()),
        *((selection_path,) if selection_path is not None else ()),
    )
    direct_output_paths = (
        manifest_path,
        clearance_path,
        restriction_path,
        derivations_path,
        summary_path,
    )
    direct_snapshots = {
        path: _read_singly_linked_regular_input(
            path, label="materialization lineage artifact"
        )
        for path in (*direct_input_paths, *direct_output_paths)
    }
    captured_artifact_bytes: dict[str, bytes] = {
        os.path.abspath(run_card_path): run_card_bytes,
        **{
            os.path.abspath(path): payload for path, payload in direct_snapshots.items()
        },
    }
    try:
        verified_preparation = _verify_completed_preparation_for_frontier(
            preparation_root=preparation_root,
            preparation_summary_path=preparation_summary_path,
            preparation_config_path=preparation_config_path,
            snapshot_manifest_path=snapshot_manifest_path,
        )
        preparation_success_bytes = _read_singly_linked_regular_input(
            verified_preparation.success_run_card_path,
            label="materialization preparation success run card",
        )
        captured_artifact_bytes[
            os.path.abspath(verified_preparation.success_run_card_path)
        ] = preparation_success_bytes
        preverified_recovery: dict[str, object] | None = None
        consolidated_recovery_selection: Sequence[Mapping[str, Any]] | None = None
        consolidated_recovery_card = (
            recovery_root / "run-cards" / "consolidate-replacement-recovery.json"
        )
        if os.path.lexists(consolidated_recovery_card):
            (
                outer_projection,
                preliminary_selection_path,
                preliminary_selection,
            ) = _materializer_consolidated_target_inputs(
                target_root=target_root,
                free_clearance_path=free_clearance_path,
                preparation_summary_path=preparation_summary_path,
                preparation_config_path=preparation_config_path,
                snapshot_manifest_path=snapshot_manifest_path,
                expected_target_count=verified_preparation.target_case_count,
            )
            preverified_recovery = cast(
                dict[str, object],
                _verify_materializer_recovery(
                    recovery_root=recovery_root,
                    selection_path=preliminary_selection_path,
                    selected_document_keys=_replacement_consolidation_selection_keys(
                        preliminary_selection
                    ),
                    purchase_policy_path=purchase_policy_path,
                    cohort_policy_path=cohort_policy_path,
                    ledger_path=ledger_path.resolve(),
                ),
            )
            raw_projection = preverified_recovery.get("target_projection")
            if not isinstance(raw_projection, Mapping):
                raise CommandError(
                    "consolidated recovery lacks authenticated target projection"
                )
            projection = _select_materializer_projection_after_recovery(
                outer_projection=outer_projection,
                recovery_projection=cast(Mapping[str, object], raw_projection),
                recovery_selection=preliminary_selection,
            )
            consolidated_recovery_selection = preliminary_selection
            if (
                len(
                    cast(
                        Sequence[Mapping[str, Any]],
                        projection["selection_records"],
                    )
                )
                != verified_preparation.target_case_count
                or free_clearance_path.resolve()
                != (target_root / "disclosure-clearance.jsonl").resolve()
            ):
                raise CommandError(
                    "consolidated recovery target projection differs from materializer"
                )
        else:
            projection = _verify_materializer_projection(
                target_root=target_root,
                free_clearance_path=free_clearance_path,
                preparation_summary_path=preparation_summary_path,
                preparation_config_path=preparation_config_path,
                snapshot_manifest_path=snapshot_manifest_path,
                expected_target_count=verified_preparation.target_case_count,
            )
        _merge_verified_artifact_bytes(
            captured_artifact_bytes,
            cast(Mapping[str, bytes], projection["verified_artifact_bytes"]),
            label="downstream materialization projection",
        )
        committed_selection_path = cast(Path, projection["selection_path"])
        if selection_path is not None and (
            selection_path.resolve() != committed_selection_path.resolve()
            or direct_snapshots[selection_path]
            != captured_artifact_bytes[os.path.abspath(committed_selection_path)]
        ):
            raise CommandError(
                "downstream selection differs from materialized target cohort"
            )
        purchase_policy = verify_case_dev_purchase_policy(
            _projection_json_object(
                direct_snapshots[purchase_policy_path], source=purchase_policy_path
            )
        )
        require_approved_case_dev_purchase_policy(
            purchase_policy, controlled_private_root=controlled_private_root
        )
        verify_case_dev_purchase_policy_cohort_binding(
            purchase_policy,
            _projection_json_object(
                direct_snapshots[cohort_policy_path], source=cohort_policy_path
            ),
        )
        purchase_authority_audit = read_case_dev_purchase_authority_audit(
            ledger_path.resolve(),
            policy=purchase_policy,
            controlled_private_root=controlled_private_root,
            initialization_receipt_path=initialization_receipt_path,
        )
        snapshot = purchase_authority_audit.snapshot
        captured_artifact_absences = tuple(
            os.path.abspath(path) for path in purchase_authority_audit.absent_paths
        )
        _merge_verified_artifact_bytes(
            captured_artifact_bytes,
            {
                os.path.abspath(path): payload
                for path, payload in purchase_authority_audit.snapshots.items()
            },
            label="downstream materializer purchase authority",
        )
        available_document_keys = cast(
            set[tuple[str, str]], projection["selected_document_keys"]
        )
        selected_document_keys = set(available_document_keys)
        docket_decision_descriptor: Any = None
        if purchase_result_path is not None and purchase_run_card_path is not None:
            authenticated_selection_keys = (
                _materializer_complete_selected_document_keys(
                    projection,
                    consolidated_recovery=preverified_recovery is not None,
                )
            )
            with CaseDevPurchaseJournal(
                ledger_path.resolve(),
                policy=purchase_policy,
                read_only=True,
                controlled_private_root=controlled_private_root,
                initialization_receipt_path=initialization_receipt_path,
            ) as journal:
                docket_decision_descriptor = (
                    _verify_materializer_docket_decision_authority(
                        selection_payload=captured_artifact_bytes[
                            os.path.abspath(committed_selection_path)
                        ],
                        snapshot_manifest_path=snapshot_manifest_path,
                        purchase_result_path=purchase_result_path,
                        purchase_run_card_path=purchase_run_card_path,
                        purchase_journal=journal,
                        purchase_policy=purchase_policy,
                        ledger_path=ledger_path.resolve(),
                        controlled_private_root=controlled_private_root,
                        initialization_receipt_path=initialization_receipt_path,
                        selected_document_count=len(authenticated_selection_keys),
                    )
                )
                _merge_verified_artifact_bytes(
                    captured_artifact_bytes,
                    {
                        os.path.abspath(path): payload
                        for path, payload in (
                            docket_decision_descriptor.source_snapshots.items()
                        )
                    },
                    label="downstream materializer docket-decision authority",
                )
                omission_keys = verified_docket_decision_document_keys(
                    docket_decision_descriptor.authority,
                    purchase_journal=journal,
                )
            if not omission_keys <= authenticated_selection_keys:
                raise CommandError(
                    "audit-only docket decision omission is outside the selection"
                )
            selected_document_keys = authenticated_selection_keys - omission_keys
        recovery = (
            preverified_recovery
            if preverified_recovery is not None
            else _verify_materializer_recovery(
                recovery_root=recovery_root,
                selection_path=projection["selection_path"],
                selected_document_keys=selected_document_keys,
                purchase_policy_path=purchase_policy_path,
                cohort_policy_path=cohort_policy_path,
                ledger_path=ledger_path,
                purchase_operations=snapshot.operations,
                purchase_committed_amount_usd=snapshot.committed_amount_usd,
                purchase_state_sha256=snapshot.purchase_state_sha256,
            )
        )
        raw_recovery_bytes = recovery.get("verified_artifact_bytes")
        if isinstance(raw_recovery_bytes, Mapping):
            _merge_verified_artifact_bytes(
                captured_artifact_bytes,
                cast(Mapping[str, bytes], raw_recovery_bytes),
                label="downstream materialization recovery",
            )
        purchased_lineage = _verify_materializer_clearance_lineage(
            manifest_path=cast(Path, recovery["manifest_path"]),
            clearance_path=purchased_clearance_path,
            run_card_path=purchased_clearance_card_path,
        )
        consolidated_resolved_capability = recovery.get(
            "consolidated_resolved_capability"
        )
        if consolidated_resolved_capability is not None:
            if (
                purchased_lineage.get("lineage_kind")
                != "replacement_recovery_consolidation"
            ):
                raise CommandError(
                    "consolidated resolved authority differs from clearance lineage"
                )
            purchased_lineage["consolidated_resolved_capability"] = (
                consolidated_resolved_capability
            )
        raw_clearance_bytes = purchased_lineage.get("verified_artifact_bytes")
        if isinstance(raw_clearance_bytes, Mapping):
            _merge_verified_artifact_bytes(
                captured_artifact_bytes,
                cast(Mapping[str, bytes], raw_clearance_bytes),
                label="downstream materialization clearance",
            )
        _verify_materializer_recovery_clearance_binding(
            recovery=recovery,
            clearance_lineage=purchased_lineage,
        )
        selection_records = cast(
            Sequence[Mapping[str, Any]], projection["selection_records"]
        )
        resolved_lineage_selection_records = (
            consolidated_recovery_selection
            if consolidated_recovery_selection is not None
            else selection_records
        )
        purchased_manifest = cast(
            Sequence[Mapping[str, Any]], recovery["manifest_records"]
        )
        needs_resolved_lineage = _selection_requires_resolved_post_recovery(
            resolved_lineage_selection_records
        ) or any(
            record.get("recovery_origin") == "unknown_status_attempt"
            for record in purchased_manifest
        )
        if needs_resolved_lineage != (resolved_path is not None):
            raise CommandError(
                "materialization lineage resolved-document input coverage differs"
            )
        resolved_records = (
            _projection_jsonl_records(
                direct_snapshots[resolved_path], source=resolved_path
            )
            if resolved_path is not None
            else []
        )
        clearance_kwargs: dict[str, Any] = {}
        if needs_resolved_lineage:
            clearance_kwargs = _materializer_clearance_lineage_kwargs(
                clearance_path=purchased_clearance_path,
                run_card_path=purchased_clearance_card_path,
                lineage=purchased_lineage,
            )
            _require_resolved_post_recovery_dispatch(
                selection_records=resolved_lineage_selection_records,
                download_records=purchased_manifest,
                clearance_records=cast(
                    Sequence[Mapping[str, Any]], purchased_lineage["clearance_records"]
                ),
                resolved_records=resolved_records,
                **clearance_kwargs,
            )
            _require_resolved_operation_bindings_dispatch(
                clearance_kwargs=clearance_kwargs,
                purchase_operation_records=snapshot.operations,
                resolved_records=resolved_records,
                expected_purchase_policy_sha256=purchase_policy.policy_sha256,
            )
        _verify_materializer_purchase_operations(
            snapshot.operations,
            purchased_manifest=purchased_manifest,
        )
        free_sources = _materializer_successor_v2_free_sources(
            projection,
            preparation_root=preparation_root,
            consolidated_recovery=preverified_recovery is not None,
        )
        materialization = prepare_cohort_document_materialization(
            (
                *free_sources,
                DocumentSource(
                    phase="purchased",
                    document_root=cast(Path, recovery["document_root"]),
                    manifest=cast(
                        Sequence[Mapping[str, Any]], recovery["manifest_records"]
                    ),
                    clearance=cast(
                        Sequence[Mapping[str, Any]],
                        purchased_lineage["clearance_records"],
                    ),
                ),
            ),
            selected_document_keys=selected_document_keys,
            output_root=materialized_root,
            resolved_post_recovery_records=resolved_records,
        )
    except (
        CaseDevPurchaseLedgerError,
        CaseDevPurchasePolicyError,
        CohortDocumentMaterializationError,
        OSError,
        ResolvedPostRecoveryError,
        sqlite3.Error,
        UnicodeError,
        ValueError,
    ) as exc:
        raise CommandError(str(exc)) from exc
    expected_manifest = _projection_jsonl_bytes(materialization.manifest)
    expected_clearance = _projection_jsonl_bytes(materialization.clearance)
    if direct_snapshots[manifest_path] != expected_manifest:
        raise CommandError("materialized manifest does not reproduce")
    if direct_snapshots[clearance_path] != expected_clearance:
        raise CommandError("materialized clearance does not reproduce")
    free_keys = {
        _materializer_record_key(record)
        for record in cast(Sequence[Mapping[str, Any]], projection["free_manifest"])
    }
    expected_restrictions = tuple(
        sorted(
            (
                *(
                    record
                    for record in cast(
                        Sequence[Mapping[str, Any]], projection["restriction_records"]
                    )
                    if _materializer_record_key(record) in free_keys
                ),
                *cast(
                    Sequence[Mapping[str, Any]],
                    purchased_lineage["restriction_records"],
                ),
            ),
            key=lambda record: (
                *_materializer_record_key(record),
                _canonical_json_sha256(record),
            ),
        )
    )
    expected_derivations = _build_materializer_derivations(
        materialization=materialization,
        free_manifest=cast(Sequence[Mapping[str, Any]], projection["free_manifest"]),
        free_clearance=cast(Sequence[Mapping[str, Any]], projection["free_clearance"]),
        purchased_manifest=cast(
            Sequence[Mapping[str, Any]], recovery["manifest_records"]
        ),
        purchased_clearance=cast(
            Sequence[Mapping[str, Any]], purchased_lineage["clearance_records"]
        ),
        resolved_records=resolved_records,
    )
    expected_restriction_bytes = _projection_jsonl_bytes(expected_restrictions)
    expected_derivation_bytes = _projection_jsonl_bytes(expected_derivations)
    if direct_snapshots[restriction_path] != expected_restriction_bytes:
        raise CommandError("materialized restriction evidence does not reproduce")
    if direct_snapshots[derivations_path] != expected_derivation_bytes:
        raise CommandError("materialization derivations do not reproduce")

    def verified_commitment(path: Path) -> dict[str, str]:
        try:
            payload = captured_artifact_bytes[os.path.abspath(path)]
        except KeyError as exc:
            raise CommandError(
                f"materialization verified snapshot lacks source: {path}"
            ) from exc
        return _file_commitment_from_bytes(path, payload)

    expected_sources: dict[str, object] = {
        "preparation_summary": verified_commitment(preparation_summary_path),
        "preparation_config": verified_commitment(preparation_config_path),
        "preparation_success_run_card": verified_commitment(
            verified_preparation.success_run_card_path
        ),
        "snapshot_manifest": verified_commitment(snapshot_manifest_path),
        "target_projection": verified_commitment(
            cast(Path, projection["summary_path"])
        ),
        "target_projection_run_card": verified_commitment(
            cast(Path, projection["run_card_path"])
        ),
        "target_selection": verified_commitment(
            cast(Path, projection["selection_path"])
        ),
        "free_download_manifest": verified_commitment(
            cast(Path, projection["free_manifest_path"])
        ),
        "free_disclosure_clearance": verified_commitment(free_clearance_path),
        **_materializer_recovery_source_commitments(recovery),
        "purchased_disclosure_clearance": verified_commitment(purchased_clearance_path),
        "purchased_clearance_run_card": verified_commitment(
            purchased_clearance_card_path
        ),
        "free_restriction_evidence": verified_commitment(
            cast(Path, projection["restriction_path"])
        ),
        "purchased_restriction_evidence": verified_commitment(
            cast(Path, purchased_lineage["restriction_path"])
        ),
        "purchase_policy": verified_commitment(purchase_policy_path),
        "cohort_policy": verified_commitment(cohort_policy_path),
        "purchase_state_sha256": snapshot.purchase_state_sha256,
        **(
            {
                "terminal_purchase_result": verified_commitment(purchase_result_path),
                "terminal_purchase_run_card": verified_commitment(
                    purchase_run_card_path
                ),
                "terminal_purchase_budget_plan": verified_commitment(
                    docket_decision_descriptor.purchase_budget_plan_path
                ),
                "docket_decision_partition": dict(docket_decision_descriptor.partition),
            }
            if docket_decision_descriptor is not None
            and purchase_result_path is not None
            and purchase_run_card_path is not None
            else {}
        ),
        **(
            {"resolved_post_recovery_documents": verified_commitment(resolved_path)}
            if resolved_path is not None
            else {}
        ),
    }
    if card.get("source_commitments") != expected_sources:
        raise CommandError("materialization source commitments do not reproduce")
    expected_docket_partition = (
        dict(docket_decision_descriptor.partition)
        if docket_decision_descriptor is not None
        else None
    )
    if card.get("docket_decision_partition") != expected_docket_partition:
        raise CommandError(
            "materialization docket-decision partition does not reproduce"
        )
    document_commitments = {
        document.destination.relative_to(document_root).as_posix(): (
            "sha256:" + _required_str(document.manifest_record, "sha256")
        )
        for document in materialization.documents
    }
    document_tree_snapshot = _materializer_tree_snapshot(document_root)
    verified_document_commitments = {
        relative_path: _bytes_sha256(payload)
        for relative_path, payload in document_tree_snapshot.items()
    }
    if verified_document_commitments != document_commitments:
        raise CommandError("materialization document-tree commitment changed")
    expected_summary = {
        **materialization.summary,
        "target_case_count": verified_preparation.target_case_count,
        **(
            {"docket_decision_partition": dict(docket_decision_descriptor.partition)}
            if docket_decision_descriptor is not None
            else {}
        ),
        "source_commitments": expected_sources,
        "output_commitments": {
            "document-downloads-merged.jsonl": _bytes_sha256(expected_manifest),
            "disclosure-clearance.jsonl": _bytes_sha256(expected_clearance),
            "restriction-evidence.jsonl": _bytes_sha256(
                _projection_jsonl_bytes(expected_restrictions)
            ),
            "materialization-derivations.jsonl": _bytes_sha256(
                _projection_jsonl_bytes(expected_derivations)
            ),
            "documents": document_commitments,
        },
        "next_stage": "plan-parse-documents",
    }
    expected_summary_bytes = _projection_json_bytes(expected_summary)
    if direct_snapshots[summary_path] != expected_summary_bytes:
        raise CommandError("materialization summary does not reproduce")
    expected_output_commitments = {
        "document_manifest": _file_commitment_from_bytes(
            manifest_path, direct_snapshots[manifest_path]
        ),
        "disclosure_clearance": _file_commitment_from_bytes(
            clearance_path, direct_snapshots[clearance_path]
        ),
        "restriction_evidence": _file_commitment_from_bytes(
            restriction_path, direct_snapshots[restriction_path]
        ),
        "materialization_derivations": _file_commitment_from_bytes(
            derivations_path, direct_snapshots[derivations_path]
        ),
        "materialization_summary": {
            "path": str(summary_path.resolve()),
            "sha256": _bytes_sha256(expected_summary_bytes),
        },
        "document_tree": document_commitments,
    }
    if card.get("output_commitments") != expected_output_commitments:
        raise CommandError("materialization output commitments do not reproduce")
    _require_snapshot_unchanged(
        {
            run_card_path: run_card_bytes,
            **direct_snapshots,
            **{
                Path(path): payload for path, payload in captured_artifact_bytes.items()
            },
            **{
                document_root / relative_path: payload
                for relative_path, payload in document_tree_snapshot.items()
            },
        },
        label="materialization lineage artifact",
    )
    return VerifiedMaterializedDownstreamLineage(
        paths=(
            run_card_path,
            restriction_path,
            derivations_path,
            *((resolved_path,) if resolved_path is not None else ()),
        ),
        artifact_bytes=dict(captured_artifact_bytes),
        absent_artifact_paths=captured_artifact_absences,
        manifest_records=tuple(
            _projection_jsonl_records(
                direct_snapshots[manifest_path], source=manifest_path
            )
        ),
        clearance_records=tuple(
            _projection_jsonl_records(
                direct_snapshots[clearance_path], source=clearance_path
            )
        ),
        selection_records=tuple(selection_records),
        resolved_lineage_selection_records=tuple(resolved_lineage_selection_records),
        resolved_records=tuple(resolved_records),
        document_tree=dict(document_tree_snapshot),
        recovered_public_capability=clearance_kwargs.get(
            "_verified_recovery_capability"
        ),
        consolidated_recovery_capability=clearance_kwargs.get(
            "_verified_consolidated_recovery_capability"
        ),
        docket_decision_authority=docket_decision_descriptor,
        verified_successor_selection_card=(
            _verified_successor_selection_card_from_projection(projection)
        ),
        authenticated_paths=authenticated_path_aliases(input_paths),
    )
