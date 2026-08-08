"""Importable recovered-public and successor-history replay helpers."""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from legalforecast.contracts.schemas import (
    DIRECT_COURTLISTENER_QUEUE_DELIVERY_AUTHORITY_V1,
)
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchasePolicy,
    CaseDevPurchaseSnapshot,
    canonical_purchase_operation_sha256,
    canonical_purchase_state_sha256,
)
from legalforecast.ingestion.replacement_recovery_source import (
    ReplacementRecoverySourceError,
    derive_recovery_source_coordinates,
)

_DEFAULT_DERIVE_RECOVERY_SOURCE_COORDINATES = derive_recovery_source_coordinates
_DEFAULT_CANONICAL_PURCHASE_OPERATION_SHA256 = canonical_purchase_operation_sha256
_DEFAULT_CANONICAL_PURCHASE_STATE_SHA256 = canonical_purchase_state_sha256


def _cli() -> Any:
    from legalforecast import cli as cli_module

    return cli_module


def _resolve_derive_recovery_source_coordinates(
    cli_module: Any,
) -> Callable[[Mapping[str, object]], Any]:
    module_derive = derive_recovery_source_coordinates
    cli_derive = cli_module.derive_recovery_source_coordinates
    if module_derive is not _DEFAULT_DERIVE_RECOVERY_SOURCE_COORDINATES:
        return cast(Callable[[Mapping[str, object]], Any], module_derive)
    if cli_derive is not _DEFAULT_DERIVE_RECOVERY_SOURCE_COORDINATES:
        return cast(Callable[[Mapping[str, object]], Any], cli_derive)
    return cast(
        Callable[[Mapping[str, object]], Any],
        _DEFAULT_DERIVE_RECOVERY_SOURCE_COORDINATES,
    )


def _resolve_canonical_purchase_operation_sha256(
    cli_module: Any,
) -> Callable[[Mapping[str, object]], str]:
    module_canonical = canonical_purchase_operation_sha256
    cli_canonical = getattr(
        cli_module,
        "canonical_purchase_operation_sha256",
        _DEFAULT_CANONICAL_PURCHASE_OPERATION_SHA256,
    )
    if module_canonical is not _DEFAULT_CANONICAL_PURCHASE_OPERATION_SHA256:
        return cast(Callable[[Mapping[str, object]], str], module_canonical)
    if cli_canonical is not _DEFAULT_CANONICAL_PURCHASE_OPERATION_SHA256:
        return cast(Callable[[Mapping[str, object]], str], cli_canonical)
    return cast(
        Callable[[Mapping[str, object]], str],
        _DEFAULT_CANONICAL_PURCHASE_OPERATION_SHA256,
    )


def _resolve_canonical_purchase_state_sha256(
    cli_module: Any,
) -> Callable[..., str]:
    module_canonical = canonical_purchase_state_sha256
    cli_canonical = getattr(
        cli_module,
        "canonical_purchase_state_sha256",
        _DEFAULT_CANONICAL_PURCHASE_STATE_SHA256,
    )
    if module_canonical is not _DEFAULT_CANONICAL_PURCHASE_STATE_SHA256:
        return cast(Callable[..., str], module_canonical)
    if cli_canonical is not _DEFAULT_CANONICAL_PURCHASE_STATE_SHA256:
        return cast(Callable[..., str], cli_canonical)
    return cast(Callable[..., str], _DEFAULT_CANONICAL_PURCHASE_STATE_SHA256)


@dataclass(frozen=True, slots=True)
class VerifiedSuccessorRecovery:
    """Cached successor-history recovery verified for one exact invocation."""

    recovery_root: Path
    selection_path: Path
    selection_bytes: bytes
    selected_document_keys: frozenset[tuple[str, str]]
    purchase_policy_path: Path
    cohort_policy_path: Path
    ledger_path: Path
    purchase_snapshot: CaseDevPurchaseSnapshot
    recovery: Mapping[str, object]

    def matches(
        self,
        *,
        recovery_root: Path,
        selection_path: Path,
        selection_bytes: bytes,
        selected_document_keys: set[tuple[str, str]],
        purchase_policy_path: Path,
        cohort_policy_path: Path,
        ledger_path: Path,
        purchase_snapshot: CaseDevPurchaseSnapshot,
    ) -> bool:
        return (
            self.recovery_root == recovery_root.resolve()
            and self.selection_path == selection_path.resolve()
            and self.selection_bytes == selection_bytes
            and self.selected_document_keys == frozenset(selected_document_keys)
            and self.purchase_policy_path == purchase_policy_path.resolve()
            and self.cohort_policy_path == cohort_policy_path.resolve()
            and self.ledger_path == ledger_path.resolve()
            and self.purchase_snapshot == purchase_snapshot
        )


def authenticated_pre_successor_purchase_snapshot(
    *,
    successor_recovery_root: Path,
    successor_controlled_private_root: Path,
    current_snapshot: CaseDevPurchaseSnapshot,
    policy: CaseDevPurchasePolicy,
    policy_artifact: Mapping[str, object],
    cohort_artifact: Mapping[str, object],
    purchase_policy_path: Path,
    cohort_policy_path: Path,
    ledger_path: Path,
    initial_controlled_private_root: Path,
    initialization_receipt_path: Path,
    capture: Callable[..., bytes],
    allowed_additional_operation_pairs: set[tuple[str, str]] | None = None,
    expected_selection_path: Path | None = None,
    expected_budget_plan_path: Path | None = None,
    expected_authority_path: Path | None = None,
    authority_transition_capability: object | None = None,
    attempt_transition_capability: object | None = None,
    verified_successor_recoveries: (
        MutableMapping[Path, VerifiedSuccessorRecovery] | None
    ) = None,
) -> tuple[CaseDevPurchaseSnapshot, Mapping[str, bytes]]:
    """Authenticate one later successor and recover its exact ledger prefix."""

    cli_module = _cli()
    recovery_card_path = (
        successor_recovery_root / "run-cards" / "recover-recap-fetch-quarantine.json"
    )
    recovery_card_bytes = capture(
        recovery_card_path, label="successor history recovery run card"
    )
    recovery_card = cli_module._projection_json_object(
        recovery_card_bytes, source=recovery_card_path
    )
    coordinates = _resolve_derive_recovery_source_coordinates(cli_module)(recovery_card)
    if coordinates.kind != "successor":
        raise ReplacementRecoverySourceError(
            "successor history recovery is not replacement_successor"
        )
    expected_lineage = (
        (coordinates.purchase_policy_path, purchase_policy_path, "purchase policy"),
        (coordinates.cohort_policy_path, cohort_policy_path, "cohort policy"),
        (coordinates.purchase_ledger_path, ledger_path, "purchase ledger"),
    )
    for committed, supplied, label in expected_lineage:
        if committed.resolve() != supplied.resolve():
            raise ReplacementRecoverySourceError(
                f"successor history {label} path rebound"
            )
    if coordinates.replacement_authority_path is None:
        raise ReplacementRecoverySourceError(
            "successor history lacks replacement purchase authority"
        )
    expected_source_paths = (
        (coordinates.selection_path, expected_selection_path, "selection"),
        (coordinates.budget_plan_path, expected_budget_plan_path, "budget plan"),
        (
            coordinates.replacement_authority_path,
            expected_authority_path,
            "purchase authority",
        ),
    )
    for committed, expected, label in expected_source_paths:
        if expected is not None and committed.resolve() != expected.resolve():
            raise ReplacementRecoverySourceError(
                f"successor history {label} path differs from its descriptor"
            )

    selection_bytes = capture(
        coordinates.selection_path, label="successor history selection"
    )
    selection_records = cli_module._projection_jsonl_records(
        selection_bytes, source=coordinates.selection_path
    )
    selected_keys = cli_module._replacement_consolidation_selection_keys(
        selection_records
    )
    budget_bytes = capture(
        coordinates.budget_plan_path, label="successor history budget plan"
    )
    budget_artifact = cli_module._projection_json_object(
        budget_bytes, source=coordinates.budget_plan_path
    )
    attempt_policy_bytes = capture(
        coordinates.attempt_policy_path, label="successor history attempt policy"
    )
    attempt_policy_artifact = cli_module._projection_json_object(
        attempt_policy_bytes, source=coordinates.attempt_policy_path
    )
    authority_bytes = capture(
        coordinates.replacement_authority_path,
        label="successor history purchase authority",
    )
    authority_artifact = cli_module._projection_json_object(
        authority_bytes, source=coordinates.replacement_authority_path
    )
    request = cli_module.verify_replacement_purchase_authority(
        authority_artifact=authority_artifact,
        controlled_private_root=successor_controlled_private_root,
        initial_purchase_policy_artifact=policy_artifact,
        initial_controlled_private_root=initial_controlled_private_root,
        cohort_policy_artifact=cohort_artifact,
        budget_plan_bytes=budget_bytes,
        selection_bytes=selection_bytes,
        purchase_ledger_path=ledger_path,
        purchase_ledger_initialization_receipt_path=initialization_receipt_path,
        allowed_additional_operation_pairs=allowed_additional_operation_pairs,
        _verified_resolved_transition_capability=(authority_transition_capability),
    )
    cli_module.verify_recap_fetch_attempt_policy(
        attempt_policy_artifact,
        purchase_policy_artifact=policy_artifact,
        cohort_policy_artifact=cohort_artifact,
        budget_plan=cli_module._missing_core_budget_plan(budget_artifact),
        budget_plan_artifact=budget_artifact,
        selection_records=selection_records,
        budget_plan_bytes=budget_bytes,
        selection_bytes=selection_bytes,
        controlled_private_root=initial_controlled_private_root,
        replacement_purchase_authority_artifact=authority_artifact,
        replacement_controlled_private_root=successor_controlled_private_root,
        purchase_ledger_initialization_receipt_path=initialization_receipt_path,
        allowed_additional_operation_pairs=allowed_additional_operation_pairs,
        _verified_resolved_transition_capability=attempt_transition_capability,
    )
    recovery = cli_module._verify_materializer_recovery(
        recovery_root=successor_recovery_root,
        selection_path=coordinates.selection_path,
        selected_document_keys=selected_keys,
        purchase_policy_path=purchase_policy_path,
        cohort_policy_path=cohort_policy_path,
        ledger_path=ledger_path,
        purchase_operations=current_snapshot.operations,
        purchase_committed_amount_usd=current_snapshot.committed_amount_usd,
        purchase_state_sha256=current_snapshot.purchase_state_sha256,
    )
    raw_recovery_bytes = recovery.get("verified_artifact_bytes")
    if not isinstance(raw_recovery_bytes, Mapping):
        raise ReplacementRecoverySourceError(
            "successor history recovery lacks authenticated artifact bytes"
        )
    if verified_successor_recoveries is not None:
        verified_successor_recoveries[successor_recovery_root.resolve()] = (
            VerifiedSuccessorRecovery(
                recovery_root=successor_recovery_root.resolve(),
                selection_path=coordinates.selection_path.resolve(),
                selection_bytes=selection_bytes,
                selected_document_keys=frozenset(selected_keys),
                purchase_policy_path=purchase_policy_path.resolve(),
                cohort_policy_path=cohort_policy_path.resolve(),
                ledger_path=ledger_path.resolve(),
                purchase_snapshot=current_snapshot,
                recovery=recovery,
            )
        )

    baseline_hashes = request.baseline_operation_record_sha256s
    if len(set(baseline_hashes)) != len(baseline_hashes):
        raise ReplacementRecoverySourceError(
            "successor history repeats a baseline purchase operation"
        )
    canonical_operation_sha256 = _resolve_canonical_purchase_operation_sha256(
        cli_module
    )
    operation_rows = tuple(
        (canonical_operation_sha256(operation), operation)
        for operation in current_snapshot.operations
    )
    if len({digest for digest, _operation in operation_rows}) != len(operation_rows):
        raise ReplacementRecoverySourceError(
            "current purchase journal repeats a canonical operation"
        )
    baseline_hash_set = set(baseline_hashes)
    baseline_rows = tuple(
        operation for digest, operation in operation_rows if digest in baseline_hash_set
    )
    if (
        tuple(canonical_operation_sha256(operation) for operation in baseline_rows)
        != baseline_hashes
    ):
        raise ReplacementRecoverySourceError(
            "successor history baseline operations are missing, changed, or reordered"
        )
    successor_rows = tuple(
        operation
        for digest, operation in operation_rows
        if digest not in baseline_hash_set
    )
    approved_pairs = cli_module._replacement_budget_operation_pairs(budget_artifact)
    baseline_pairs = {
        (
            cli_module._required_str(operation, "candidate_id"),
            cli_module._required_str(operation, "source_document_id"),
        )
        for operation in baseline_rows
    }
    if baseline_pairs & approved_pairs:
        raise ReplacementRecoverySourceError(
            "successor history overlaps a baseline purchase operation"
        )
    observed_pairs = {
        (
            cli_module._required_str(operation, "candidate_id"),
            cli_module._required_str(operation, "source_document_id"),
        )
        for operation in successor_rows
    }
    if len(observed_pairs) != len(successor_rows) or observed_pairs != approved_pairs:
        raise ReplacementRecoverySourceError(
            "current purchase journal does not exactly partition successor history"
        )
    canonical_state_sha256 = _resolve_canonical_purchase_state_sha256(cli_module)
    baseline_state_sha256 = canonical_state_sha256(
        policy,
        committed_amount_usd=request.committed_spend_usd,
        operations=baseline_rows,
    )
    if request.purchase_journal_state_sha256 != "sha256:" + baseline_state_sha256:
        raise ReplacementRecoverySourceError(
            "authenticated successor baseline purchase state does not reproduce"
        )
    return (
        CaseDevPurchaseSnapshot(
            operations=baseline_rows,
            committed_amount_usd=request.committed_spend_usd,
            purchase_state_sha256=baseline_state_sha256,
        ),
        cast(Mapping[str, bytes], raw_recovery_bytes),
    )


def recovered_public_lineage_digest(value: object, *, label: str) -> str:
    """Convert one canonical artifact commitment to the bare lineage form."""

    if (
        not isinstance(value, str)
        or re.fullmatch(r"sha256:[0-9a-f]{64}", value) is None
    ):
        raise ValueError(
            f"recovered-public {label} must be a canonical SHA-256 commitment"
        )
    return value.removeprefix("sha256:")


def direct_queue_delivery_lineage(
    operation: Mapping[str, Any],
    *,
    purchase_policy_sha256: str | None,
    recovery_run_card_sha256: str,
    recovery_manifest_sha256: str,
    recovery_restriction_sha256: str,
    purchase_state_sha256: str,
) -> dict[str, object]:
    """Project direct queued delivery only from an authenticated journal row."""

    cli_module = _cli()
    if operation.get("public_material_recovery") is not None:
        return {}
    raw_response = operation.get("response")
    raw_material = operation.get("material_evidence")
    operation_key = operation.get("operation_key")
    if not isinstance(raw_response, Mapping) or not isinstance(raw_material, Mapping):
        return {}
    response = cast(Mapping[str, Any], raw_response)
    material = cast(Mapping[str, Any], raw_material)
    response_keys = set(response)
    base_response_keys = {
        "source_provider",
        "reservation_usd",
        "queue_id",
        "reservation_id",
    }
    allowed_response_keys = base_response_keys | {
        "courtlistener_url_commitment_correction"
    }
    queue_id = response.get("queue_id")
    reservation_usd = response.get("reservation_usd")
    queue_response_sha256 = material.get("queue_response_sha256")
    if (
        operation.get("status") != "queued"
        or operation.get("actual_usd") is not None
        or operation.get("reconciliation") is not None
        or operation.get("error") is not None
        or response.get("source_provider") != "courtlistener.recap-fetch+pacer"
        or not isinstance(purchase_policy_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", purchase_policy_sha256) is None
        or (
            response_keys != base_response_keys
            and response_keys != allowed_response_keys
        )
        or "broker_receipts" in response
        or not isinstance(operation_key, str)
        or re.fullmatch(
            r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
            operation_key,
        )
        is None
        or not isinstance(queue_id, str)
        or re.fullmatch(r"[1-9][0-9]*", queue_id) is None
        or response.get("reservation_id") != f"direct:{operation_key}"
        or not isinstance(reservation_usd, str)
        or reservation_usd != operation.get("reservation_usd")
        or not isinstance(queue_response_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", queue_response_sha256) is None
    ):
        return {}
    authority: dict[str, object] = {
        "schema_version": str(DIRECT_COURTLISTENER_QUEUE_DELIVERY_AUTHORITY_V1),
        "source_provider": "courtlistener.recap-fetch+pacer",
        "purchase_status": "queued",
        "operation_key": operation_key,
        "queue_id": queue_id,
        "reservation_id": f"direct:{operation_key}",
        "reservation_usd": reservation_usd,
        "queue_response_sha256": queue_response_sha256,
        "purchase_policy_sha256": purchase_policy_sha256,
        "purchase_operation_sha256": recovered_public_lineage_digest(
            cli_module._canonical_json_sha256(operation), label="purchase operation"
        ),
        "purchase_response_sha256": recovered_public_lineage_digest(
            cli_module._canonical_json_sha256(response), label="purchase response"
        ),
        "recovery_run_card_sha256": recovery_run_card_sha256,
        "recovery_manifest_sha256": recovery_manifest_sha256,
        "recovery_restriction_evidence_sha256": recovery_restriction_sha256,
        "purchase_state_sha256": purchase_state_sha256,
    }
    return {"direct_queue_delivery_authority": authority}


def derive_recovered_public_lineage_rows(
    recovery: Mapping[str, object],
    *,
    expected_manifest_path: Path,
    expected_restriction_path: Path,
) -> list[dict[str, object]]:
    """Rebuild recovered-public evidence only from authenticated source bytes."""

    cli_module = _cli()
    raw_verified = recovery.get("verified_artifact_bytes")
    raw_manifest_records = recovery.get("manifest_records")
    recovery_run_card_path = recovery.get("run_card_path")
    if (
        not isinstance(raw_verified, Mapping)
        or not isinstance(raw_manifest_records, Sequence)
        or isinstance(raw_manifest_records, (str, bytes))
        or not all(
            isinstance(record, Mapping)
            for record in cast(Sequence[object], raw_manifest_records)
        )
        or not isinstance(recovery_run_card_path, Path)
    ):
        raise ValueError("recovered-public verification lacks exact recovery bytes")
    verified_bytes = cast(Mapping[str, bytes], raw_verified)
    manifest_records = cast(Sequence[Mapping[str, Any]], raw_manifest_records)
    try:
        recovery_run_card_bytes = verified_bytes[
            os.path.abspath(recovery_run_card_path)
        ]
        recovery_manifest_bytes = verified_bytes[
            os.path.abspath(expected_manifest_path)
        ]
        restriction_bytes = verified_bytes[os.path.abspath(expected_restriction_path)]
    except KeyError as exc:
        raise ValueError(
            "recovered-public verification lacks exact recovery bytes"
        ) from exc
    recovery_run_card = cli_module._projection_json_object(
        recovery_run_card_bytes, source=recovery_run_card_path
    )
    raw_outputs = recovery_run_card.get("output_commitments")
    raw_historical_operations = recovery.get("historical_purchase_operations")
    historical_state_sha256 = recovery.get("historical_purchase_state_sha256")
    purchase_policy_sha256 = recovery.get("purchase_policy_sha256")
    if (
        not isinstance(raw_outputs, Mapping)
        or not isinstance(raw_historical_operations, Sequence)
        or isinstance(raw_historical_operations, (str, bytes))
        or not all(
            isinstance(operation, Mapping)
            for operation in cast(Sequence[object], raw_historical_operations)
        )
        or not isinstance(historical_state_sha256, str)
        or cast(Mapping[str, object], raw_outputs).get("purchase_state_sha256")
        != historical_state_sha256
    ):
        raise ValueError("recovered-public purchase state changed after recovery")
    operations = cli_module._materializer_record_index(
        cast(Sequence[Mapping[str, Any]], raw_historical_operations),
        label="recovered-public purchase operations",
    )
    restrictions = cli_module._materializer_record_index(
        cli_module._projection_jsonl_records(
            restriction_bytes, source=expected_restriction_path
        ),
        label="recovered-public restriction evidence",
    )
    recovery_run_card_sha256 = recovered_public_lineage_digest(
        cli_module._bytes_sha256(recovery_run_card_bytes), label="recovery run card"
    )
    recovery_manifest_sha256 = recovered_public_lineage_digest(
        cli_module._bytes_sha256(recovery_manifest_bytes), label="recovery manifest"
    )
    recovery_restriction_sha256 = recovered_public_lineage_digest(
        cli_module._bytes_sha256(restriction_bytes),
        label="recovery restriction evidence",
    )
    lineage_rows: list[dict[str, object]] = []
    for manifest_record in manifest_records:
        key = cli_module._materializer_record_key(manifest_record)
        operation = operations.get(key)
        restriction = restrictions.get(key)
        if operation is None or restriction is None:
            raise ValueError(
                f"recovered-public recovery lacks exact purchase evidence: {key}"
            )
        material = operation.get("material_evidence")
        operation_key = operation.get("operation_key")
        fresh_recap_detail_sha256 = manifest_record.get("fresh_recap_detail_sha256")
        if (
            not isinstance(material, Mapping)
            or not isinstance(operation_key, str)
            or operation_key != manifest_record.get("purchase_operation_key")
            or not isinstance(fresh_recap_detail_sha256, str)
            or cast(Mapping[str, object], material).get("provider_detail_sha256")
            != fresh_recap_detail_sha256
            or restriction.get("fresh_recap_detail_sha256") != fresh_recap_detail_sha256
        ):
            raise ValueError(
                f"recovered-public purchase or fresh-detail identity changed: {key}"
            )
        lineage_rows.append(
            {
                "candidate_id": key[0],
                "source_document_id": key[1],
                "recovery_run_card_sha256": recovery_run_card_sha256,
                "recovery_manifest_sha256": recovery_manifest_sha256,
                "recovery_restriction_evidence_sha256": recovery_restriction_sha256,
                "purchase_state_sha256": historical_state_sha256,
                "purchase_operation_sha256": recovered_public_lineage_digest(
                    cli_module._canonical_json_sha256(operation),
                    label="purchase operation",
                ),
                "purchase_operation_key": operation_key,
                "fresh_recap_detail_sha256": fresh_recap_detail_sha256,
                **direct_queue_delivery_lineage(
                    operation,
                    purchase_policy_sha256=(
                        purchase_policy_sha256
                        if isinstance(purchase_policy_sha256, str)
                        else None
                    ),
                    recovery_run_card_sha256=recovery_run_card_sha256,
                    recovery_manifest_sha256=recovery_manifest_sha256,
                    recovery_restriction_sha256=recovery_restriction_sha256,
                    purchase_state_sha256=historical_state_sha256,
                ),
            }
        )
    return lineage_rows


def authenticate_recovered_public_raw_evidence(
    *,
    recovery_root: Path,
    run_card_path: Path,
    selection_path: Path,
    purchase_policy_path: Path,
    cohort_policy_path: Path,
    ledger_path: Path,
    initialization_receipt_path: Path,
    controlled_private_root: Path | None,
    successor_history_recovery_root: Path | None = None,
    successor_history_controlled_private_root: Path | None = None,
    authority_transition_capability: object | None = None,
    attempt_transition_capability: object | None = None,
    resolved_transition_prior_snapshot: CaseDevPurchaseSnapshot | None = None,
) -> Mapping[str, object]:
    """Authenticate recovery bytes, policies, and live ledger state together."""

    cli_module = _cli()
    verified_bytes: dict[str, bytes] = {}

    def capture(path: Path, *, label: str) -> bytes:
        payload = cli_module._read_singly_linked_regular_input(path, label=label)
        cli_module._merge_verified_artifact_bytes(
            verified_bytes,
            {os.path.abspath(path): payload},
            label="recovered-public successor history",
        )
        return payload

    selection_records = cli_module._projection_jsonl_records(
        capture(selection_path, label="recovered-public selection"),
        source=selection_path,
    )
    purchase_policy_bytes = capture(
        purchase_policy_path, label="recovered-public purchase policy"
    )
    purchase_policy_artifact = cli_module._projection_json_object(
        purchase_policy_bytes, source=purchase_policy_path
    )
    purchase_policy = cli_module.verify_case_dev_purchase_policy(
        purchase_policy_artifact
    )
    cli_module.require_approved_case_dev_purchase_policy(
        purchase_policy, controlled_private_root=controlled_private_root
    )
    cohort_policy_bytes = capture(
        cohort_policy_path, label="recovered-public cohort policy"
    )
    cohort_policy_artifact = cli_module._projection_json_object(
        cohort_policy_bytes, source=cohort_policy_path
    )
    cli_module.verify_case_dev_purchase_policy_cohort_binding(
        purchase_policy,
        cohort_policy_artifact,
    )
    if ledger_path.resolve() != purchase_policy.canonical_ledger_path:
        raise ValueError(
            "--purchase-ledger conflicts with the canonical policy locator"
        )
    purchase_snapshot = cli_module.read_case_dev_purchase_snapshot(
        ledger_path.resolve(),
        policy=purchase_policy,
        controlled_private_root=controlled_private_root,
        initialization_receipt_path=initialization_receipt_path,
    )
    history_roots = (
        successor_history_recovery_root,
        successor_history_controlled_private_root,
    )
    if any(path is not None for path in history_roots) and not all(
        path is not None for path in history_roots
    ):
        raise ValueError(
            "successor history recovery and controlled-private roots must be "
            "supplied together"
        )
    transition_inputs = (
        authority_transition_capability,
        attempt_transition_capability,
        resolved_transition_prior_snapshot,
    )
    has_successor_history = all(path is not None for path in history_roots)
    transition_shape_valid = all(value is None for value in transition_inputs) or (
        authority_transition_capability is not None
        and (
            resolved_transition_prior_snapshot is not None
            and attempt_transition_capability is not None
            if has_successor_history
            else (
                resolved_transition_prior_snapshot is None
                and attempt_transition_capability is None
            )
        )
    )
    if not transition_shape_valid:
        raise ValueError("resolved transition replay capability shape differs")
    verification_snapshot = purchase_snapshot
    history: dict[str, object] | None = None
    if (
        successor_history_recovery_root is not None
        and successor_history_controlled_private_root is not None
    ):
        if controlled_private_root is None:
            raise ValueError(
                "successor history requires --controlled-private-root for the "
                "initial purchase authority"
            )
        successor_history_authenticator = authenticated_pre_successor_purchase_snapshot
        cli_override = getattr(
            cli_module, "_authenticated_pre_successor_purchase_snapshot", None
        )
        if callable(cli_override) and not (
            getattr(cli_override, "__module__", None) == "legalforecast.cli"
            and getattr(cli_override, "__name__", None)
            == "_authenticated_pre_successor_purchase_snapshot"
        ):
            successor_history_authenticator = cast(Any, cli_override)
        verification_snapshot, history_recovery_bytes = successor_history_authenticator(
            successor_recovery_root=successor_history_recovery_root,
            successor_controlled_private_root=(
                successor_history_controlled_private_root
            ),
            current_snapshot=(resolved_transition_prior_snapshot or purchase_snapshot),
            policy=purchase_policy,
            policy_artifact=purchase_policy_artifact,
            cohort_artifact=cohort_policy_artifact,
            purchase_policy_path=purchase_policy_path,
            cohort_policy_path=cohort_policy_path,
            ledger_path=ledger_path.resolve(),
            initial_controlled_private_root=controlled_private_root,
            initialization_receipt_path=initialization_receipt_path,
            capture=capture,
            authority_transition_capability=(authority_transition_capability),
            attempt_transition_capability=attempt_transition_capability,
        )
        cli_module._merge_verified_artifact_bytes(
            verified_bytes,
            history_recovery_bytes,
            label="recovered-public successor history",
        )
        history = {
            "recovery_root": successor_history_recovery_root.resolve(),
            "initial_controlled_private_root": controlled_private_root.resolve(),
            "controlled_private_root": (
                successor_history_controlled_private_root.resolve()
            ),
            "replayed_purchase_state_sha256": (
                verification_snapshot.purchase_state_sha256
            ),
            "source_paths": tuple(
                sorted(
                    (Path(path).resolve() for path in history_recovery_bytes),
                    key=str,
                )
            ),
        }
    elif authority_transition_capability is not None:
        verification_snapshot = (
            cli_module._consume_live_resolved_transition_prior_snapshot(
                authority_transition_capability
            )
        )
    recovery = cli_module._verify_materializer_quarantine_recovery(
        recovery_root=recovery_root,
        run_card_path=run_card_path,
        selection_path=selection_path,
        selected_document_keys=cli_module._replacement_consolidation_selection_keys(
            selection_records
        ),
        purchase_policy_path=purchase_policy_path,
        cohort_policy_path=cohort_policy_path,
        ledger_path=ledger_path.resolve(),
        purchase_operations=verification_snapshot.operations,
        purchase_committed_amount_usd=verification_snapshot.committed_amount_usd,
        purchase_state_sha256=verification_snapshot.purchase_state_sha256,
    )
    raw_recovery_bytes = recovery.get("verified_artifact_bytes")
    if not isinstance(raw_recovery_bytes, Mapping):
        raise ValueError("recovered-public verification lacks exact recovery bytes")
    cli_module._merge_verified_artifact_bytes(
        verified_bytes,
        cast(Mapping[str, bytes], raw_recovery_bytes),
        label="recovered-public recovery",
    )
    result = dict(recovery)
    result["verified_artifact_bytes"] = verified_bytes
    if history is not None:
        result["authenticated_successor_history"] = history
    return result
