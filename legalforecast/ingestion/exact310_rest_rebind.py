"""Thin policy/spec layer for the exact 310-docket terminal REST rebind."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import MappingProxyType
from typing import cast

from legalforecast.ingestion.cycle_acquisition_store import (
    CandidateObservation,
    CycleAcquisitionStore,
    CycleAcquisitionStoreError,
    cohort_reason_policy_taxonomy,
)
from legalforecast.ingestion.rest_observation_policy_rebind import (
    AuthenticatedTerminalRestSource,
    PublishedTerminalRestRebind,
    RestObservationPolicyRebindError,
    TerminalRestRebindOutcome,
    authenticate_terminal_rest_source,
    canonical_rebind_sha256,
    load_pinned_rebind_json,
    publish_authenticated_terminal_rest_rebind,
    write_new_rebind_json,
)
from legalforecast.ingestion.strict_screen_evidence import (
    StrictScreenEvidenceError,
    validate_strict_screen_evidence,
)

CONTRACT_SCHEMA = "legalforecast.exact310_terminal_rest_rebind_contract.v1"
RUN_CARD_SCHEMA = "legalforecast.exact310_terminal_rest_rebind_run.v1"
STAGE_NAME = "exact310-terminal-rest-policy-rebind"
FAIL_CLOSED_REASON = "policy_rebind_evidence_insufficient"
SOURCE_CYCLE_HASH = "9fde3c19a93aa69d6e3bbb6d6597022bad0da24eb86613c6f95a16c222273b83"
SOURCE_BATCH_ID = "cycle1-courtlistener-20260711-to-20260715-rest-screen-v1"
SOURCE_CANDIDATE_COUNT = 310
SOURCE_CANDIDATE_SET_SHA256 = (
    "79816511e35ae06e3b99e9ea679e0b1a4fb7d10afdd30c6c1dbea818076291ee"
)
TRANSFER_RECEIPT_SHA256 = (
    "ac1196ee01f71f4a0488db28f9b92dbd2f3f6578a95ddfa6cb832e70b12ccffc"
)


class Exact310RestRebindError(ValueError):
    """Raised when exact310 authority or current-policy proof does not reconcile."""


@dataclass(frozen=True, slots=True)
class Exact310SourceSpec:
    """Externally fixed source identity, replaceable only in focused tests."""

    cycle_hash: str = SOURCE_CYCLE_HASH
    batch_id: str = SOURCE_BATCH_ID
    candidate_count: int = SOURCE_CANDIDATE_COUNT
    candidate_set_sha256: str = SOURCE_CANDIDATE_SET_SHA256
    transfer_receipt_sha256: str = TRANSFER_RECEIPT_SHA256


OFFICIAL_EXACT310_SOURCE_SPEC = Exact310SourceSpec()


@dataclass(frozen=True, slots=True)
class Exact310PlanResult:
    """Immutable provider-free planning result."""

    contract_path: Path
    contract_sha256: str
    preserve_current_count: int
    reproved_current_count: int
    reproved_exclusion_count: int
    fail_closed_count: int


@dataclass(frozen=True, slots=True)
class Exact310RebindResult:
    """Current-cycle snapshot and immutable run card."""

    snapshot_path: Path
    snapshot_manifest_sha256: str
    run_card_path: Path
    run_card_sha256: str
    preserve_current_count: int
    reproved_current_count: int
    reproved_exclusion_count: int
    fail_closed_count: int
    provider_activity_executed: bool = False
    paid_activity_executed: bool = False


@dataclass(frozen=True, slots=True)
class _Target:
    cycle_hash: str
    cycle_policy: Mapping[str, object]
    batch_id: str
    batch_digest: str
    candidate_ids: frozenset[str]
    current: Mapping[str, CandidateObservation]


def plan_exact310_terminal_rest_rebind(
    *,
    source_store_path: str | Path,
    source_snapshot_path: str | Path,
    expected_source_snapshot_manifest_sha256: str,
    transfer_receipt_path: str | Path,
    target_store_path: str | Path,
    target_batch_id: str,
    expected_target_cycle_hash: str,
    contract_output_path: str | Path,
    source_spec: Exact310SourceSpec = OFFICIAL_EXACT310_SOURCE_SPEC,
) -> Exact310PlanResult:
    """Authenticate exact source/target state and freeze all derived outcomes."""

    contract, outcomes = _build_contract(
        source_store_path=source_store_path,
        source_snapshot_path=source_snapshot_path,
        expected_source_snapshot_manifest_sha256=(
            expected_source_snapshot_manifest_sha256
        ),
        transfer_receipt_path=transfer_receipt_path,
        target_store_path=target_store_path,
        target_batch_id=target_batch_id,
        expected_target_cycle_hash=expected_target_cycle_hash,
        source_spec=source_spec,
    )
    contract_path = Path(contract_output_path).resolve()
    contract_sha256 = write_new_rebind_json(contract_path, contract)
    counts = _action_counts(outcomes)
    return Exact310PlanResult(
        contract_path=contract_path,
        contract_sha256=contract_sha256,
        preserve_current_count=counts["preserve_current"],
        reproved_current_count=counts["reprove_current"],
        reproved_exclusion_count=counts["reprove_exclusion"],
        fail_closed_count=counts["fail_closed"],
    )


def execute_exact310_terminal_rest_rebind(
    *,
    source_store_path: str | Path,
    source_snapshot_path: str | Path,
    expected_source_snapshot_manifest_sha256: str,
    transfer_receipt_path: str | Path,
    target_store_path: str | Path,
    target_batch_id: str,
    expected_target_cycle_hash: str,
    contract_path: str | Path,
    expected_contract_sha256: str,
    snapshot_output_root: str | Path,
    snapshot_id: str,
    run_card_path: str | Path,
    source_spec: Exact310SourceSpec = OFFICIAL_EXACT310_SOURCE_SPEC,
) -> Exact310RebindResult:
    """Publish the exact pinned outcomes without any provider or paid activity."""

    pinned = load_pinned_rebind_json(
        contract_path,
        expected_sha256=expected_contract_sha256,
        label="exact310 rebind contract",
    )
    _validate_contract(pinned)
    pinned_actions = {
        _text(row, "candidate_id"): _text(row, "policy_action")
        for row in _outcome_rows(pinned)
    }
    contract, outcomes = _build_contract(
        source_store_path=source_store_path,
        source_snapshot_path=source_snapshot_path,
        expected_source_snapshot_manifest_sha256=(
            expected_source_snapshot_manifest_sha256
        ),
        transfer_receipt_path=transfer_receipt_path,
        target_store_path=target_store_path,
        target_batch_id=target_batch_id,
        expected_target_cycle_hash=expected_target_cycle_hash,
        source_spec=source_spec,
        pinned_actions=pinned_actions,
    )
    if contract != pinned:
        raise Exact310RestRebindError(
            "live source, target, or derived outcomes differ from pinned contract"
        )
    run_card_target = Path(run_card_path).resolve()
    if run_card_target.exists():
        raise Exact310RestRebindError(f"run card already exists: {run_card_target}")
    stage_commitments = {
        "stage": STAGE_NAME,
        "contract_sha256": expected_contract_sha256,
        "source_cycle_hash": source_spec.cycle_hash,
        "source_batch_id": source_spec.batch_id,
        "source_snapshot_manifest_sha256": (expected_source_snapshot_manifest_sha256),
        "source_candidate_set_sha256": source_spec.candidate_set_sha256,
        "transfer_receipt_sha256": source_spec.transfer_receipt_sha256,
        "source_observations_sha256": contract["source_observations_sha256"],
        "target_cycle_hash": expected_target_cycle_hash,
        "target_batch_id": target_batch_id,
        "target_outcomes_sha256": contract["target_outcomes_sha256"],
        **{f"{key}_count": value for key, value in _action_counts(outcomes).items()},
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
    }
    try:
        published = publish_authenticated_terminal_rest_rebind(
            target_store_path=target_store_path,
            target_batch_id=target_batch_id,
            expected_target_cycle_hash=expected_target_cycle_hash,
            expected_target_cycle_policy=_mapping(contract, "target_cycle_policy"),
            expected_candidate_ids=frozenset(
                outcome.candidate_id for outcome in outcomes
            ),
            outcomes=outcomes,
            snapshot_output_root=snapshot_output_root,
            snapshot_id=snapshot_id,
            stage_commitments=stage_commitments,
        )
    except RestObservationPolicyRebindError as exc:
        raise Exact310RestRebindError(str(exc)) from exc
    counts = _action_counts(outcomes)
    run_card = _run_card(
        published=published,
        contract_path=Path(contract_path).resolve(),
        contract_sha256=expected_contract_sha256,
        source_store_path=Path(source_store_path).resolve(),
        source_snapshot_path=Path(source_snapshot_path).resolve(),
        transfer_receipt_path=Path(transfer_receipt_path).resolve(),
        target_store_path=Path(target_store_path).resolve(),
        target_batch_id=target_batch_id,
        counts=counts,
    )
    run_card_sha256 = write_new_rebind_json(run_card_target, run_card)
    return Exact310RebindResult(
        snapshot_path=published.snapshot_path,
        snapshot_manifest_sha256=published.snapshot_manifest_sha256,
        run_card_path=run_card_target,
        run_card_sha256=run_card_sha256,
        preserve_current_count=counts["preserve_current"],
        reproved_current_count=counts["reprove_current"],
        reproved_exclusion_count=counts["reprove_exclusion"],
        fail_closed_count=counts["fail_closed"],
    )


def _build_contract(
    *,
    source_store_path: str | Path,
    source_snapshot_path: str | Path,
    expected_source_snapshot_manifest_sha256: str,
    transfer_receipt_path: str | Path,
    target_store_path: str | Path,
    target_batch_id: str,
    expected_target_cycle_hash: str,
    source_spec: Exact310SourceSpec,
    pinned_actions: Mapping[str, str] | None = None,
) -> tuple[Mapping[str, object], tuple[TerminalRestRebindOutcome, ...]]:
    try:
        with CycleAcquisitionStore(source_store_path, read_only=True):
            pass
    except (CycleAcquisitionStoreError, OSError) as exc:
        raise Exact310RestRebindError(
            f"source store is not writer-free and WAL-clean: {exc}"
        ) from exc
    receipt = load_pinned_rebind_json(
        transfer_receipt_path,
        expected_sha256=source_spec.transfer_receipt_sha256,
        label="exact310 transfer receipt",
    )
    _validate_receipt(receipt, source_spec)
    try:
        source = authenticate_terminal_rest_source(
            source_store_path=source_store_path,
            source_snapshot_path=source_snapshot_path,
            expected_snapshot_manifest_sha256=(
                expected_source_snapshot_manifest_sha256
            ),
            expected_cycle_hash=source_spec.cycle_hash,
            expected_cycle_policy=None,
            expected_batch_id=source_spec.batch_id,
        )
    except RestObservationPolicyRebindError as exc:
        raise Exact310RestRebindError(str(exc)) from exc
    if len(source.candidate_ids) != source_spec.candidate_count:
        raise Exact310RestRebindError("exact310 source candidate count mismatch")
    if source.raw_candidate_ids:
        raise Exact310RestRebindError(
            "exact310 compatibility source unexpectedly contains raw artifacts"
        )
    _validate_source_batch_config(source.batch_config, receipt, source_spec)
    recomputed_candidate_set_sha256 = _recompute_source_candidate_set_sha256(
        source.discovery_payloads,
        receipt=receipt,
        spec=source_spec,
    )
    target = _target(
        target_store_path,
        target_batch_id=target_batch_id,
        expected_cycle_hash=expected_target_cycle_hash,
        candidate_ids=source.candidate_ids,
    )
    outcomes = _derive_outcomes(source, target, pinned_actions=pinned_actions)
    rows = [
        _outcome_record(outcome, source.observations[outcome.candidate_id])
        for outcome in outcomes
    ]
    source_rows = [
        {
            "candidate_id": candidate_id,
            "observation_sha256": canonical_rebind_sha256(
                source.observations[candidate_id]
            ),
        }
        for candidate_id in sorted(source.candidate_ids)
    ]
    contract: Mapping[str, object] = {
        "schema_version": CONTRACT_SCHEMA,
        "stage": STAGE_NAME,
        "source_cycle_hash": source.cycle_hash,
        "source_batch_id": source.batch_id,
        "source_batch_digest": source.batch_digest,
        "source_batch_config": dict(source.batch_config),
        "source_snapshot_manifest_sha256": source.snapshot_manifest_sha256,
        "source_candidate_set_sha256": recomputed_candidate_set_sha256,
        "transfer_receipt_sha256": source_spec.transfer_receipt_sha256,
        "candidate_count": len(source.candidate_ids),
        "candidate_ids_sha256": canonical_rebind_sha256(sorted(source.candidate_ids)),
        "source_observations_sha256": canonical_rebind_sha256(source_rows),
        "target_cycle_hash": target.cycle_hash,
        "target_cycle_policy": dict(target.cycle_policy),
        "target_batch_id": target.batch_id,
        "target_batch_digest": target.batch_digest,
        "target_outcomes_sha256": canonical_rebind_sha256(rows),
        "outcomes": rows,
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
    }
    return MappingProxyType(contract), outcomes


def _derive_outcomes(
    source: AuthenticatedTerminalRestSource,
    target: _Target,
    *,
    pinned_actions: Mapping[str, str] | None,
) -> tuple[TerminalRestRebindOutcome, ...]:
    outcomes: list[TerminalRestRebindOutcome] = []
    for candidate_id in sorted(source.candidate_ids):
        source_row = source.observations[candidate_id]
        current = target.current.get(candidate_id)
        policy_action = (
            None if pinned_actions is None else pinned_actions.get(candidate_id)
        )
        if current is not None and policy_action not in {
            "reprove_current",
            "reprove_exclusion",
            "fail_closed",
        }:
            outcomes.append(_preserve(current))
            continue
        if policy_action is None:
            if source_row.get("state") == "excluded" and _exclusion_reason_supported(
                source_row
            ):
                policy_action = "reprove_exclusion"
            elif _strict_evidence_is_valid(
                source_row,
                target_cycle_policy=target.cycle_policy,
            ):
                policy_action = "reprove_current"
            else:
                policy_action = "fail_closed"
        if policy_action == "reprove_current":
            outcome = _reproved(source_row, source, target)
        elif policy_action == "reprove_exclusion":
            outcome = _reproved_exclusion(source_row, source, target)
        else:
            outcome = _failed_closed(source_row, source, target)
        outcomes.append(outcome)
    return tuple(outcomes)


def _exclusion_reason_supported(source_row: Mapping[str, object]) -> bool:
    reason = source_row.get("reason_code")
    taxonomy = cohort_reason_policy_taxonomy()
    supported = set(taxonomy["immutable_reason_codes"])
    supported.update(taxonomy["refreshable_reason_codes"])
    return isinstance(reason, str) and reason in supported


def _strict_evidence_is_valid(
    source_row: Mapping[str, object],
    *,
    target_cycle_policy: Mapping[str, object],
) -> bool:
    evidence = _mapping(source_row, "evidence")
    candidate_id = _text(source_row, "candidate_id")
    try:
        validate_strict_screen_evidence(
            evidence,
            expected_candidate_id=candidate_id,
        )
        target_anchor_value = target_cycle_policy.get("eligibility_anchor")
        disposition_value = evidence.get("first_written_mtd_disposition_date")
        if not isinstance(target_anchor_value, str) or not isinstance(
            disposition_value, str
        ):
            return False
        if date.fromisoformat(disposition_value) < date.fromisoformat(
            target_anchor_value
        ):
            return False
    except (StrictScreenEvidenceError, ValueError):
        return False
    return True


def _reproved(
    source_row: Mapping[str, object],
    source: AuthenticatedTerminalRestSource,
    target: _Target,
) -> TerminalRestRebindOutcome:
    evidence = dict(_mapping(source_row, "evidence"))
    evidence["policy_rebind"] = _policy_proof(
        source_row, source, target, current_policy_proof_available=True
    )
    return TerminalRestRebindOutcome(
        candidate_id=_text(source_row, "candidate_id"),
        action="write",
        state="accepted",
        reason_code="strict_clean_screen_passed",
        evidence=evidence,
        observed_at=_text(source_row, "observed_at"),
    )


def _failed_closed(
    source_row: Mapping[str, object],
    source: AuthenticatedTerminalRestSource,
    target: _Target,
) -> TerminalRestRebindOutcome:
    candidate_id = _text(source_row, "candidate_id")
    return TerminalRestRebindOutcome(
        candidate_id=candidate_id,
        action="write",
        state="excluded",
        reason_code=FAIL_CLOSED_REASON,
        evidence={
            "candidate_id": candidate_id,
            "source_terminal_observation": {
                "state": source_row["state"],
                "reason_code": source_row["reason_code"],
                "evidence": dict(_mapping(source_row, "evidence")),
            },
            "policy_rebind": _policy_proof(
                source_row, source, target, current_policy_proof_available=False
            ),
        },
        observed_at=_text(source_row, "observed_at"),
    )


def _reproved_exclusion(
    source_row: Mapping[str, object],
    source: AuthenticatedTerminalRestSource,
    target: _Target,
) -> TerminalRestRebindOutcome:
    evidence = dict(_mapping(source_row, "evidence"))
    evidence["policy_rebind"] = _policy_proof(
        source_row,
        source,
        target,
        current_policy_proof_available=True,
        strategy="authenticated_exclusion_evidence_reproof_v1",
    )
    return TerminalRestRebindOutcome(
        candidate_id=_text(source_row, "candidate_id"),
        action="write",
        state="excluded",
        reason_code=_text(source_row, "reason_code"),
        evidence=evidence,
        observed_at=_text(source_row, "observed_at"),
    )


def _preserve(current: CandidateObservation) -> TerminalRestRebindOutcome:
    return TerminalRestRebindOutcome(
        candidate_id=current.candidate_id,
        action="preserve_current",
        state=current.state,
        reason_code=current.reason_code,
        evidence=dict(current.evidence),
        observed_at=current.observed_at,
    )


def _policy_proof(
    source_row: Mapping[str, object],
    source: AuthenticatedTerminalRestSource,
    target: _Target,
    *,
    current_policy_proof_available: bool,
    strategy: str | None = None,
) -> Mapping[str, object]:
    return {
        "strategy": strategy
        or (
            "authenticated_strict_evidence_reproof_v1"
            if current_policy_proof_available
            else "fail_closed_without_current_policy_proof_v1"
        ),
        "source_cycle_hash": source.cycle_hash,
        "source_batch_id": source.batch_id,
        "source_snapshot_manifest_sha256": source.snapshot_manifest_sha256,
        "source_observation_sha256": canonical_rebind_sha256(source_row),
        "source_state": source_row["state"],
        "source_reason_code": source_row["reason_code"],
        "target_cycle_hash": target.cycle_hash,
        "current_policy_proof_available": current_policy_proof_available,
        "raw_artifact_count": 0,
    }


def _target(
    store_path: str | Path,
    *,
    target_batch_id: str,
    expected_cycle_hash: str,
    candidate_ids: frozenset[str],
) -> _Target:
    try:
        with CycleAcquisitionStore(store_path, read_only=True) as store:
            if store.cycle_hash != expected_cycle_hash:
                raise Exact310RestRebindError("target cycle hash mismatch")
            if set(store.candidate_ids(target_batch_id)) != set(candidate_ids):
                raise Exact310RestRebindError("target candidate set mismatch")
            current = {
                candidate_id: observation
                for candidate_id in sorted(candidate_ids)
                if (observation := store.current_observation(candidate_id)) is not None
            }
            if any(
                row.state not in {"accepted", "excluded"} for row in current.values()
            ):
                raise Exact310RestRebindError("target has unsupported current state")
            return _Target(
                cycle_hash=store.cycle_hash,
                cycle_policy=MappingProxyType(dict(store.cycle_policy)),
                batch_id=target_batch_id,
                batch_digest=store.batch_digest(target_batch_id),
                candidate_ids=candidate_ids,
                current=MappingProxyType(current),
            )
    except Exact310RestRebindError:
        raise
    except (CycleAcquisitionStoreError, KeyError, OSError) as exc:
        raise Exact310RestRebindError(f"cannot authenticate target: {exc}") from exc


def _validate_receipt(receipt: Mapping[str, object], spec: Exact310SourceSpec) -> None:
    expected = {
        "schema_version": "legalforecast.direct_search_seed_result.v1",
        "batch_id": spec.batch_id,
        "leads_seeded": spec.candidate_count,
        "leads_selected": spec.candidate_count,
        "source_candidate_set_sha256": spec.candidate_set_sha256,
    }
    if any(receipt.get(key) != value for key, value in expected.items()):
        raise Exact310RestRebindError("transfer receipt source identity mismatch")
    for key in ("source_batch_id", "source_batch_digest", "term"):
        _text(receipt, key)


def _validate_source_batch_config(
    config: Mapping[str, object],
    receipt: Mapping[str, object],
    spec: Exact310SourceSpec,
) -> None:
    expected = {
        "auth_mode": "authenticated",
        "decision_window_end": "2026-07-15",
        "decision_window_start": "2026-07-11",
        "discovery_mode": ("legalforecast.courtlistener_direct_search_transfer.v1"),
        "order_by": "entry_date_filed desc",
        "page_size": 100,
        "provider": "courtlistener-recap-rest-v4",
        "query_field": "description",
        "query_term_order_is_frozen": True,
        "query_terms": [_text(receipt, "term")],
        "schema_version": "legalforecast.recap_api_discovery_batch.v1",
        "search_type": "rd",
        "source_batch_digest": _text(receipt, "source_batch_digest"),
        "source_batch_id": _text(receipt, "source_batch_id"),
        "source_candidate_count": spec.candidate_count,
        "source_candidate_set_sha256": spec.candidate_set_sha256,
        "top_k_per_term": spec.candidate_count,
    }
    if dict(config) != expected:
        raise Exact310RestRebindError(
            "source batch config does not match pinned transfer authority"
        )


def _recompute_source_candidate_set_sha256(
    discovery_payloads: Mapping[str, tuple[Mapping[str, object], ...]],
    *,
    receipt: Mapping[str, object],
    spec: Exact310SourceSpec,
) -> str:
    """Rebuild the direct-search lead commitment from authenticated payloads."""

    if len(discovery_payloads) != spec.candidate_count:
        raise Exact310RestRebindError(
            "source discovery payload candidate count mismatch"
        )
    source_batch_id = _text(receipt, "source_batch_id")
    source_batch_digest = _text(receipt, "source_batch_digest")
    transfer_term = _text(receipt, "term")
    records: list[Mapping[str, object]] = []
    numeric_docket_ids: set[int] = set()
    for candidate_id, candidate_payloads in discovery_payloads.items():
        if len(candidate_payloads) != 1:
            raise Exact310RestRebindError(
                f"source candidate {candidate_id} does not have exactly one "
                "transfer discovery payload"
            )
        payload = candidate_payloads[0]
        docket_id = _text(payload, "docket_id")
        try:
            numeric_docket_id = int(docket_id)
        except ValueError as exc:
            raise Exact310RestRebindError(
                f"source candidate {candidate_id} has a nonnumeric docket ID"
            ) from exc
        if numeric_docket_id < 1 or str(numeric_docket_id) != docket_id:
            raise Exact310RestRebindError(
                f"source candidate {candidate_id} has a noncanonical docket ID"
            )
        if numeric_docket_id in numeric_docket_ids:
            raise Exact310RestRebindError(
                "source discovery payload docket ID collision"
            )
        numeric_docket_ids.add(numeric_docket_id)
        if (
            candidate_id != f"courtlistener-docket-{docket_id}"
            or payload.get("candidate_id") != candidate_id
            or payload.get("courtlistener_docket_id") != docket_id
            or payload.get("provider") != "courtlistener-recap-rest-v4"
            or payload.get("query_term") != transfer_term
        ):
            raise Exact310RestRebindError(
                f"source discovery payload identity mismatch for {candidate_id}"
            )
        provenance = _mapping(payload, "direct_search_provenance")
        expected_provenance = {
            "schema_version": "legalforecast.courtlistener_direct_search_transfer.v1",
            "source_batch_id": source_batch_id,
            "source_batch_digest": source_batch_digest,
            "source_candidate_set_sha256": spec.candidate_set_sha256,
        }
        if any(
            provenance.get(key) != expected
            for key, expected in expected_provenance.items()
        ):
            raise Exact310RestRebindError(
                f"source discovery provenance mismatch for {candidate_id}"
            )
        source_hits_value = provenance.get("source_hits")
        if not isinstance(source_hits_value, list) or not source_hits_value:
            raise Exact310RestRebindError(
                f"source discovery provenance has no source hits for {candidate_id}"
            )
        source_hits = [
            _validated_source_hit(hit, candidate_id=candidate_id)
            for hit in cast(list[object], source_hits_value)
        ]
        if source_hits != sorted(
            source_hits,
            key=lambda hit: (
                cast(str, hit["query_term"]),
                cast(str, hit["provider_hit_id"]),
                cast(str, hit["payload_sha256"]),
            ),
        ) or len({canonical_rebind_sha256(hit) for hit in source_hits}) != len(
            source_hits
        ):
            raise Exact310RestRebindError(
                f"source discovery provenance hits are not unique and sorted for "
                f"{candidate_id}"
            )
        primary_hit = {
            "provider_hit_id": _text(provenance, "source_provider_hit_id"),
            "query_term": _text(provenance, "source_query_term"),
            "payload_sha256": _text(provenance, "source_payload_sha256"),
        }
        if primary_hit not in source_hits:
            raise Exact310RestRebindError(
                f"source discovery primary hit is not committed for {candidate_id}"
            )
        records.append(
            {
                "docket_id": docket_id,
                "court_id": _optional_text(payload.get("court_id"), "court_id"),
                "docket_number": _optional_text(
                    payload.get("docket_number"), "docket_number"
                ),
                "case_name": _optional_text(payload.get("case_name"), "case_name"),
                "decision_entry_evidence": _optional_mapping(
                    payload.get("decision_entry_evidence"),
                    "decision_entry_evidence",
                ),
                "source_hits": source_hits,
            }
        )
    records.sort(key=lambda row: int(cast(str, row["docket_id"])))
    recomputed = canonical_rebind_sha256(records)
    if recomputed != spec.candidate_set_sha256:
        raise Exact310RestRebindError(
            "source discovery payload candidate-set commitment mismatch"
        )
    return recomputed


def _validated_source_hit(
    value: object,
    *,
    candidate_id: str,
) -> Mapping[str, object]:
    hit = _as_mapping(value, f"source hit for {candidate_id}")
    if set(hit) != {"provider_hit_id", "query_term", "payload_sha256"}:
        raise Exact310RestRebindError(
            f"source discovery provenance hit field mismatch for {candidate_id}"
        )
    payload_sha256 = _text(hit, "payload_sha256")
    if len(payload_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in payload_sha256
    ):
        raise Exact310RestRebindError(
            f"source discovery provenance hit digest mismatch for {candidate_id}"
        )
    return MappingProxyType(
        {
            "provider_hit_id": _text(hit, "provider_hit_id"),
            "query_term": _text(hit, "query_term"),
            "payload_sha256": payload_sha256,
        }
    )


def _optional_text(value: object, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise Exact310RestRebindError(f"{label} must be non-empty text or null")
    return value


def _optional_mapping(value: object, label: str) -> Mapping[str, object] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise Exact310RestRebindError(f"{label} must be an object or absent")
    return dict(cast(Mapping[str, object], value))


def _validate_contract(contract: Mapping[str, object]) -> None:
    if contract.get("schema_version") != CONTRACT_SCHEMA:
        raise Exact310RestRebindError("contract schema mismatch")
    rows = _outcome_rows(contract)
    if contract.get("candidate_count") != len(rows):
        raise Exact310RestRebindError("contract candidate count mismatch")
    if contract.get("target_outcomes_sha256") != canonical_rebind_sha256(rows):
        raise Exact310RestRebindError("contract target outcome commitment mismatch")
    for key in (
        "provider_activity_requested",
        "provider_activity_executed",
        "paid_activity_requested",
        "paid_activity_executed",
    ):
        if contract.get(key) is not False:
            raise Exact310RestRebindError("contract cannot authorize provider activity")


def _outcome_record(
    outcome: TerminalRestRebindOutcome,
    source_row: Mapping[str, object],
) -> Mapping[str, object]:
    return {
        "candidate_id": outcome.candidate_id,
        "policy_action": _policy_action(outcome),
        "source_observation_sha256": canonical_rebind_sha256(source_row),
        "target_observation_sha256": canonical_rebind_sha256(outcome.projection()),
    }


def _outcome_rows(contract: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    value = contract.get("outcomes")
    if not isinstance(value, list):
        raise Exact310RestRebindError("contract outcomes must be a list")
    rows = cast(list[object], value)
    return tuple(_as_mapping(row, "contract outcome") for row in rows)


def _action_counts(
    outcomes: Sequence[TerminalRestRebindOutcome],
) -> dict[str, int]:
    counts = {
        "preserve_current": 0,
        "reprove_current": 0,
        "reprove_exclusion": 0,
        "fail_closed": 0,
    }
    for outcome in outcomes:
        counts[_policy_action(outcome)] += 1
    return counts


def _policy_action(outcome: TerminalRestRebindOutcome) -> str:
    if outcome.action == "preserve_current":
        return "preserve_current"
    if outcome.state == "accepted":
        return "reprove_current"
    if outcome.reason_code == FAIL_CLOSED_REASON:
        return "fail_closed"
    return "reprove_exclusion"


def _run_card(
    *,
    published: PublishedTerminalRestRebind,
    contract_path: Path,
    contract_sha256: str,
    source_store_path: Path,
    source_snapshot_path: Path,
    transfer_receipt_path: Path,
    target_store_path: Path,
    target_batch_id: str,
    counts: Mapping[str, int],
) -> Mapping[str, object]:
    return {
        "schema_version": RUN_CARD_SCHEMA,
        "stage": STAGE_NAME,
        "contract_path": str(contract_path),
        "contract_sha256": contract_sha256,
        "source_store_path": str(source_store_path),
        "source_snapshot_path": str(source_snapshot_path),
        "transfer_receipt_path": str(transfer_receipt_path),
        "target_store_path": str(target_store_path),
        "target_batch_id": target_batch_id,
        "snapshot_path": str(published.snapshot_path),
        "snapshot_manifest_sha256": published.snapshot_manifest_sha256,
        **{f"{key}_count": value for key, value in counts.items()},
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "pacer_fee_acknowledgment_requested": False,
        "pacer_fee_acknowledgment_executed": False,
    }


def _mapping(value: Mapping[str, object], key: str) -> Mapping[str, object]:
    nested = value.get(key)
    if not isinstance(nested, Mapping):
        raise Exact310RestRebindError(f"{key} must be an object")
    return cast(Mapping[str, object], nested)


def _as_mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise Exact310RestRebindError(f"{label} must be an object")
    return cast(Mapping[str, object], value)


def _text(value: Mapping[str, object], key: str) -> str:
    text = value.get(key)
    if not isinstance(text, str) or not text:
        raise Exact310RestRebindError(f"{key} must be non-empty text")
    return text
