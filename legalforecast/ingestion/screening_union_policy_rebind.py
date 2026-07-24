"""Exact provider-free policy rebind for an authenticated screening union."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.cycle_acquisition_store import (
    CycleAcquisitionStore,
    CycleAcquisitionStoreError,
    DiscoveryHit,
    TermTerminalStatus,
    cohort_reason_policy_taxonomy,
    verify_snapshot,
)
from legalforecast.ingestion.firecrawl_screening_identity import (
    firecrawl_screening_implementation,
    screening_union_policy_rebind_implementation,
    validate_firecrawl_screening_implementation,
)
from legalforecast.ingestion.screening_snapshot_union import (
    UnionCandidate,
    load_verified_screening_snapshot,
)
from legalforecast.ingestion.strict_screen_evidence import (
    StrictScreenEvidenceError,
    validate_strict_screen_evidence,
)

STAGE_NAME = "rebind-screening-union-policy"
RUN_CARD_SCHEMA = "legalforecast.screening_union_policy_rebind_run.v1"
POLICY_PROOF_SCHEMA = "legalforecast.screening_union_policy_rebind_proof.v1"
POLICY_DELTA_NAME = "restricted_material_public_hearing_false_positive_fix_v1"
SOURCE_RESTRICTED_MATERIAL_SHA256 = (
    "f36a0cf5b5db5e3d6d997d46095cccfde89be9a9213db6b26576a116ed16758d"
)
TARGET_RESTRICTED_MATERIAL_SHA256 = (
    "e74b77e817675b58a18a7f4afbdff785ea5669564ccf95f9246023347dc1fbe2"
)
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_CANDIDATE_ID = re.compile(r"courtlistener-docket-([0-9]+)\Z")
_UNION_STAGE_SCHEMA = "legalforecast.screening_snapshot_union_inputs.v2"
_UNION_RUN_SCHEMA = "legalforecast.screening_snapshot_union_summary.v1"
_UNION_SOURCE_PATH = "legalforecast/ingestion/screening_snapshot_union.py"
_AUDITED_IMPLEMENTATION_PREDECESSOR_SHA256 = {
    "legalforecast/cli.py": (
        "14020dcb3064993fdf81ad680e52ccf71f21ee69b639d0222f53a31c56ab8291"
    ),
    "legalforecast/ingestion/firecrawl_screening_identity.py": (
        "a8ea3f63d58df42b8f2993bac3b46119095584f9c47740a699d90bd5be857b32"
    ),
    _UNION_SOURCE_PATH: (
        "c95f22b456dda41dc7575ad50da638fb59adb27276aebe571ba3d036a9f23bc3"
    ),
    "legalforecast/ingestion/strict_screen_evidence.py": (
        "135663c6a0e666e440d3b269b7a608062799ae5830f06dfc810c99bdda4026f3"
    ),
}
_TERM = "authenticated-screening-union-policy-rebind"


class ScreeningUnionPolicyRebindError(ValueError):
    """Raised when union lineage or the one allowed policy transition is invalid."""


@dataclass(frozen=True, slots=True)
class ScreeningUnionPolicyRebindResult:
    """One current-cycle terminal snapshot and its immutable audit card."""

    snapshot_path: Path
    snapshot_manifest_sha256: str
    run_card_path: Path
    run_card_sha256: str
    candidate_count: int
    accepted_count: int
    excluded_count: int
    raw_artifact_count: int
    provider_activity_executed: bool = False
    paid_activity_executed: bool = False


def rebind_screening_union_policy(
    *,
    source_snapshot_path: str | Path,
    expected_source_snapshot_manifest_sha256: str,
    source_union_run_card_path: str | Path,
    expected_source_union_run_card_sha256: str,
    source_cycle_store_path: str | Path,
    expected_source_cycle_hash: str,
    target_cycle_store_path: str | Path,
    expected_target_cycle_hash: str,
    target_batch_id: str,
    snapshot_output_root: str | Path,
    snapshot_id: str,
    raw_artifact_output_root: str | Path,
    run_card_path: str | Path,
) -> ScreeningUnionPolicyRebindResult:
    """Rebind one exact union whose policy hash lagged its proven implementation."""

    for value, label in (
        (
            expected_source_snapshot_manifest_sha256,
            "source snapshot manifest SHA-256",
        ),
        (expected_source_union_run_card_sha256, "source union run-card SHA-256"),
        (expected_source_cycle_hash, "source cycle hash"),
        (expected_target_cycle_hash, "target cycle hash"),
    ):
        _require_sha256(value, label)
    _require_path_component(snapshot_id, "target snapshot ID")
    if not target_batch_id.strip():
        raise ScreeningUnionPolicyRebindError("target batch ID must not be blank")
    source_snapshot = _safe_directory(
        Path(source_snapshot_path), "source screening union snapshot"
    )
    source_run_card_path = _safe_regular_file(
        Path(source_union_run_card_path), "source union run card"
    )
    source_cycle_store_path = _safe_regular_file(
        Path(source_cycle_store_path), "source cycle store"
    )
    target_cycle_store_path = _safe_regular_file(
        Path(target_cycle_store_path), "target cycle store"
    )
    snapshot_root = _safe_output_path(
        Path(snapshot_output_root), "target snapshot root"
    )
    raw_output_root = _safe_output_path(
        Path(raw_artifact_output_root), "raw artifact output"
    )
    run_card_target = _safe_output_path(Path(run_card_path), "target run card")
    snapshot_path = snapshot_root / snapshot_id
    _verify_disjoint_paths(
        immutable_inputs=(
            source_snapshot,
            source_run_card_path,
            source_cycle_store_path,
        ),
        target_cycle_store=target_cycle_store_path,
        owned_outputs=(snapshot_root, raw_output_root, run_card_target),
    )
    source_run_card_payload = _read_regular_file(
        source_run_card_path, "source union run card"
    )
    source_run_card_sha256 = hashlib.sha256(source_run_card_payload).hexdigest()
    if source_run_card_sha256 != expected_source_union_run_card_sha256:
        raise ScreeningUnionPolicyRebindError("source union run-card SHA-256 mismatch")
    source_run_card = _json_object(source_run_card_payload, "source union run card")
    source = load_verified_screening_snapshot(
        source_snapshot,
        expected_manifest_sha256=expected_source_snapshot_manifest_sha256,
        expected_cycle_hash=expected_source_cycle_hash,
    )
    _verify_union_authority(
        source_snapshot=source_snapshot,
        source_manifest=source.manifest,
        source_run_card=source_run_card,
        expected_source_manifest_sha256=expected_source_snapshot_manifest_sha256,
        source_cycle_store=source_cycle_store_path,
    )

    with CycleAcquisitionStore(source_cycle_store_path, read_only=True) as source_store:
        if source_store.cycle_hash != expected_source_cycle_hash:
            raise ScreeningUnionPolicyRebindError("source cycle-store hash mismatch")
        source_policy = dict(source_store.cycle_policy)
    with CycleAcquisitionStore(target_cycle_store_path) as target_store:
        if target_store.cycle_hash != expected_target_cycle_hash:
            raise ScreeningUnionPolicyRebindError("target cycle-store hash mismatch")
        target_policy = dict(target_store.cycle_policy)
    delta = _verify_allowed_policy_delta(
        source_policy=source_policy,
        target_policy=target_policy,
        source_manifest=source.manifest,
    )
    source_stage_commitments = cast(
        Mapping[str, object], source.manifest["stage_commitments"]
    )
    source_union_commitment = cast(
        Mapping[str, object],
        source_stage_commitments["screening_snapshot_union_inputs"],
    )
    current_screening_implementation = firecrawl_screening_implementation()

    accepted_count = 0
    excluded_count = 0
    rebound_candidates: list[tuple[UnionCandidate, Mapping[str, object]]] = []
    target_anchor = _policy_anchor(target_policy)
    taxonomy = cohort_reason_policy_taxonomy()
    excluded_reasons = {
        *taxonomy["immutable_reason_codes"],
        *taxonomy["refreshable_reason_codes"],
    }
    source_outcome_rows: list[Mapping[str, object]] = []
    target_outcome_rows: list[Mapping[str, object]] = []
    for candidate in source.candidates:
        _validate_candidate_id(candidate.candidate_id)
        if candidate.state == "accepted":
            if candidate.reason_code != "strict_clean_screen_passed":
                raise ScreeningUnionPolicyRebindError(
                    f"accepted source candidate has invalid reason: "
                    f"{candidate.candidate_id}"
                )
            try:
                validate_strict_screen_evidence(
                    candidate.evidence,
                    expected_candidate_id=candidate.candidate_id,
                )
            except StrictScreenEvidenceError as exc:
                raise ScreeningUnionPolicyRebindError(str(exc)) from exc
            disposition = _evidence_date(
                candidate.evidence,
                "first_written_mtd_disposition_date",
                candidate.candidate_id,
            )
            if disposition < target_anchor:
                raise ScreeningUnionPolicyRebindError(
                    "accepted source candidate predates target anchor: "
                    f"{candidate.candidate_id}"
                )
            accepted_count += 1
        elif candidate.state == "excluded":
            if candidate.reason_code not in excluded_reasons:
                raise ScreeningUnionPolicyRebindError(
                    f"excluded source candidate has unsupported reason "
                    f"{candidate.reason_code!r}: {candidate.candidate_id}"
                )
            excluded_count += 1
        else:
            raise ScreeningUnionPolicyRebindError(
                f"source union contains unsupported terminal state "
                f"{candidate.state!r}: {candidate.candidate_id}"
            )
        source_terminal_sha256 = _canonical_sha256(
            {
                "candidate_id": candidate.candidate_id,
                "observation_id": candidate.observation_id,
                "observed_at": candidate.observed_at,
                "state": candidate.state,
                "reason_code": candidate.reason_code,
                "evidence": dict(candidate.evidence),
            }
        )
        evidence = dict(candidate.evidence)
        evidence["screening_union_policy_rebind"] = {
            "schema_version": POLICY_PROOF_SCHEMA,
            "policy_delta": POLICY_DELTA_NAME,
            "source_cycle_hash": expected_source_cycle_hash,
            "source_snapshot_manifest_sha256": (
                expected_source_snapshot_manifest_sha256
            ),
            "source_terminal_sha256": source_terminal_sha256,
            "target_cycle_hash": expected_target_cycle_hash,
            "current_policy_proof_available": True,
            "provider_activity_requested": False,
            "provider_activity_executed": False,
            "paid_activity_requested": False,
            "paid_activity_executed": False,
        }
        rebound_candidates.append((candidate, evidence))
        source_outcome_rows.append(
            {
                "candidate_id": candidate.candidate_id,
                "observation_id": candidate.observation_id,
                "observed_at": candidate.observed_at,
                "terminal_sha256": source_terminal_sha256,
            }
        )
        target_outcome_rows.append(
            {
                "candidate_id": candidate.candidate_id,
                "state": candidate.state,
                "reason_code": candidate.reason_code,
                "observed_at": candidate.observed_at,
                "evidence_sha256": _canonical_sha256(evidence),
            }
        )
    if accepted_count + excluded_count != len(source.candidates):
        raise ScreeningUnionPolicyRebindError(
            "source union terminal outcomes do not reconcile"
        )

    raw_root = _ensure_directory(raw_output_root, "raw artifact output")
    candidate_ids = {candidate.candidate_id for candidate in source.candidates}
    raw_records: list[Mapping[str, object]] = []
    stage_commitment: dict[str, object] = {
        "schema_version": RUN_CARD_SCHEMA,
        "stage": STAGE_NAME,
        "implementation": screening_union_policy_rebind_implementation(),
        "policy_delta": delta,
        "source_cycle_hash": expected_source_cycle_hash,
        "source_snapshot_manifest_sha256": (expected_source_snapshot_manifest_sha256),
        "source_union_run_card_sha256": expected_source_union_run_card_sha256,
        "source_candidate_count": len(source.candidates),
        "source_outcomes_sha256": _canonical_sha256(source_outcome_rows),
        "source_raw_artifact_count": len(source.raw_artifacts),
        "source_raw_artifacts_sha256": _canonical_sha256(
            [
                {
                    "candidate_id": artifact.candidate_id,
                    "sha256": artifact.sha256,
                    "byte_count": artifact.byte_count,
                    "retrieved_at": artifact.retrieved_at,
                }
                for artifact in source.raw_artifacts
            ]
        ),
        "target_cycle_hash": expected_target_cycle_hash,
        "target_outcomes_sha256": _canonical_sha256(target_outcome_rows),
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
    }
    try:
        with CycleAcquisitionStore(target_cycle_store_path) as target_store:
            if target_store.cycle_hash != expected_target_cycle_hash:
                raise ScreeningUnionPolicyRebindError(
                    "target cycle changed during rebind"
                )
            batch_digest = target_store.ensure_batch(
                target_batch_id,
                {
                    "stage": STAGE_NAME,
                    "source_authority": stage_commitment,
                },
            )
            target_store.ensure_terms(target_batch_id, (_TERM,))
            target_store.commit_search_page(
                target_batch_id,
                _TERM,
                None,
                tuple(
                    DiscoveryHit(
                        provider_hit_id=f"union-policy-rebind:{candidate.candidate_id}",
                        candidate_id=candidate.candidate_id,
                        payload=dict(candidate.evidence),
                    )
                    for candidate in source.candidates
                ),
                next_cursor=None,
                terminal_status=TermTerminalStatus.EXHAUSTED,
            )
            for artifact in source.raw_artifacts:
                if artifact.candidate_id not in candidate_ids:
                    raise ScreeningUnionPolicyRebindError(
                        "source raw artifact lacks a candidate owner"
                    )
                destination = (
                    raw_root / artifact.candidate_id / f"{artifact.sha256}.html"
                )
                committed = target_store.write_raw_artifact(
                    artifact.candidate_id,
                    destination,
                    artifact.content,
                    retrieved_at=artifact.retrieved_at,
                )
                if committed.path.resolve() != destination.resolve():
                    committed = target_store.rehome_raw_artifact(
                        artifact.candidate_id,
                        destination,
                        artifact.content,
                    )
                if (
                    committed.sha256 != artifact.sha256
                    or committed.byte_count != artifact.byte_count
                    or committed.retrieved_at != artifact.retrieved_at
                ):
                    raise ScreeningUnionPolicyRebindError(
                        "target raw artifact commitment mismatch"
                    )
                raw_records.append(
                    {
                        "candidate_id": committed.candidate_id,
                        "sha256": committed.sha256,
                        "byte_count": committed.byte_count,
                        "retrieved_at": committed.retrieved_at,
                    }
                )
            _verify_owned_raw_tree(
                raw_root,
                expected_paths={
                    (
                        raw_root / artifact.candidate_id / f"{artifact.sha256}.html"
                    ).resolve()
                    for artifact in source.raw_artifacts
                },
            )
            for candidate, evidence in rebound_candidates:
                existing_observation = target_store.batch_terminal_observation(
                    target_batch_id, candidate.candidate_id
                )
                if existing_observation is not None:
                    if (
                        existing_observation.state != candidate.state
                        or existing_observation.reason_code != candidate.reason_code
                        or dict(existing_observation.evidence) != dict(evidence)
                        or existing_observation.observed_at != candidate.observed_at
                    ):
                        raise ScreeningUnionPolicyRebindError(
                            "target batch contains conflicting replay evidence for "
                            f"{candidate.candidate_id}"
                        )
                    continue
                target_store.record_observation(
                    candidate.candidate_id,
                    batch_id=target_batch_id,
                    state=candidate.state,
                    reason_code=candidate.reason_code,
                    evidence=evidence,
                    observed_at=candidate.observed_at,
                    audit_immutable_skip=False,
                )
            if not target_store.snapshot_is_saturated(target_batch_id):
                raise ScreeningUnionPolicyRebindError(
                    "target policy-rebind batch is not saturated"
                )
            stage_commitment["target_batch_digest"] = batch_digest
            stage_commitment["target_raw_artifacts_sha256"] = _canonical_sha256(
                raw_records
            )
            target_stage_commitments: dict[str, object] = {
                "screening_snapshot_union_inputs": source_union_commitment,
                "firecrawl_screening_implementation": (
                    current_screening_implementation
                ),
                "screening_union_policy_rebind": stage_commitment,
            }
            existing_snapshot = target_store.existing_complete_snapshot(
                snapshot_root,
                snapshot_id=snapshot_id,
                batch_id=target_batch_id,
            )
            if existing_snapshot is None:
                if snapshot_path.exists():
                    raise ScreeningUnionPolicyRebindError(
                        "target snapshot path exists without matching store "
                        f"registration: {snapshot_path}"
                    )
                snapshot_path = target_store.export_snapshot(
                    snapshot_root,
                    snapshot_id=snapshot_id,
                    batch_id=target_batch_id,
                    complete=True,
                    stage_commitments=target_stage_commitments,
                )
            else:
                snapshot_path = existing_snapshot[0]
            manifest = verify_snapshot(
                snapshot_path,
                expected_cycle_hash=expected_target_cycle_hash,
                expected_batch_digest=batch_digest,
                require_complete=True,
                require_saturated=True,
            )
    except (CycleAcquisitionStoreError, OSError) as exc:
        raise ScreeningUnionPolicyRebindError(str(exc)) from exc
    manifest_payload = _read_regular_file(
        snapshot_path / "manifest.json", "target snapshot manifest"
    )
    snapshot_manifest_sha256 = hashlib.sha256(manifest_payload).hexdigest()
    if manifest.get("stage_commitments") != target_stage_commitments:
        raise ScreeningUnionPolicyRebindError(
            "target snapshot stage commitment mismatch"
        )
    run_card: Mapping[str, object] = {
        "schema_version": RUN_CARD_SCHEMA,
        "stage": STAGE_NAME,
        "source_snapshot_path": str(source_snapshot),
        "source_snapshot_manifest_sha256": (expected_source_snapshot_manifest_sha256),
        "source_union_run_card_path": str(source_run_card_path),
        "source_union_run_card_sha256": expected_source_union_run_card_sha256,
        "source_cycle_store_path": str(Path(source_cycle_store_path).resolve()),
        "source_cycle_hash": expected_source_cycle_hash,
        "target_cycle_store_path": str(Path(target_cycle_store_path).resolve()),
        "target_cycle_hash": expected_target_cycle_hash,
        "target_batch_id": target_batch_id,
        "target_batch_digest": stage_commitment["target_batch_digest"],
        "target_snapshot_path": str(snapshot_path),
        "target_snapshot_manifest_sha256": snapshot_manifest_sha256,
        "candidate_count": len(source.candidates),
        "accepted_count": accepted_count,
        "excluded_count": excluded_count,
        "raw_artifact_count": len(source.raw_artifacts),
        "policy_delta": delta,
        "source_outcomes_sha256": stage_commitment["source_outcomes_sha256"],
        "target_outcomes_sha256": stage_commitment["target_outcomes_sha256"],
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "reconciled": True,
    }
    run_card_sha256 = _write_new_json(run_card_target, run_card)
    return ScreeningUnionPolicyRebindResult(
        snapshot_path=snapshot_path,
        snapshot_manifest_sha256=snapshot_manifest_sha256,
        run_card_path=run_card_target,
        run_card_sha256=run_card_sha256,
        candidate_count=len(source.candidates),
        accepted_count=accepted_count,
        excluded_count=excluded_count,
        raw_artifact_count=len(source.raw_artifacts),
    )


def _verify_union_authority(
    *,
    source_snapshot: Path,
    source_manifest: Mapping[str, Any],
    source_run_card: Mapping[str, Any],
    expected_source_manifest_sha256: str,
    source_cycle_store: Path,
) -> None:
    stage_commitments_value = source_manifest.get("stage_commitments")
    if not isinstance(stage_commitments_value, Mapping):
        raise ScreeningUnionPolicyRebindError("source snapshot lacks stage commitments")
    stage_commitments = cast(Mapping[str, object], stage_commitments_value)
    union_value = stage_commitments.get("screening_snapshot_union_inputs")
    if not isinstance(union_value, Mapping):
        raise ScreeningUnionPolicyRebindError(
            "source snapshot is not a screening union"
        )
    union = cast(Mapping[str, object], union_value)
    candidate_count = source_manifest["files"]["candidates.jsonl"]["row_count"]
    if (
        union.get("schema_version") != _UNION_STAGE_SCHEMA
        or union.get("candidate_count") != candidate_count
        or not isinstance(union.get("source_count"), int)
        or cast(int, union["source_count"]) < 2
    ):
        raise ScreeningUnionPolicyRebindError(
            "source screening-union commitment is invalid"
        )
    implementation_value = stage_commitments.get("firecrawl_screening_implementation")
    if not isinstance(implementation_value, Mapping):
        raise ScreeningUnionPolicyRebindError(
            "source union lacks screening implementation authority"
        )
    try:
        source_implementation = validate_firecrawl_screening_implementation(
            cast(Mapping[str, object], implementation_value),
            require_current=False,
        )
    except ValueError as exc:
        raise ScreeningUnionPolicyRebindError(str(exc)) from exc
    current_implementation = firecrawl_screening_implementation()
    source_hashes = cast(Mapping[str, object], source_implementation["source_sha256"])
    current_hashes = cast(Mapping[str, object], current_implementation["source_sha256"])
    if set(source_hashes) != set(current_hashes):
        raise ScreeningUnionPolicyRebindError(
            "source union screening implementation source set changed"
        )
    for path in source_hashes:
        if source_hashes[path] == current_hashes[path]:
            continue
        if _AUDITED_IMPLEMENTATION_PREDECESSOR_SHA256.get(path) != source_hashes[path]:
            raise ScreeningUnionPolicyRebindError(
                "source union screening implementation differs outside the "
                "audited verifier and policy-rebind wrapper additions"
            )
    if source_run_card.get("schema_version") != _UNION_RUN_SCHEMA:
        raise ScreeningUnionPolicyRebindError(
            "source union run card has the wrong schema"
        )
    required = {
        "stage": "union-screening-snapshots",
        "status": "completed",
        "dry_run": False,
        "snapshot_complete": True,
        "snapshot_saturated": True,
        "reconciled": True,
        "candidate_count": candidate_count,
        "accepted_case_count": source_manifest["files"]["screened-cases.jsonl"][
            "row_count"
        ],
        "excluded_case_count": source_manifest["files"]["exclusions.jsonl"][
            "row_count"
        ],
        "provider_access_requested": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
    }
    if any(source_run_card.get(key) != value for key, value in required.items()):
        raise ScreeningUnionPolicyRebindError(
            "source union run card does not prove one terminal provider-free union"
        )
    output_paths = source_run_card.get("output_paths")
    if not isinstance(output_paths, list) or str(source_snapshot) not in output_paths:
        raise ScreeningUnionPolicyRebindError(
            "source union run card does not bind the source snapshot"
        )
    input_paths = source_run_card.get("input_paths")
    if not isinstance(input_paths, list) or str(source_cycle_store) not in input_paths:
        raise ScreeningUnionPolicyRebindError(
            "source union run card does not bind the source cycle store"
        )
    if (
        hashlib.sha256(
            _read_regular_file(
                source_snapshot / "manifest.json", "source snapshot manifest"
            )
        ).hexdigest()
        != expected_source_manifest_sha256
    ):
        raise ScreeningUnionPolicyRebindError(
            "source snapshot changed after run-card verification"
        )
    output_commitments = source_run_card.get("output_commitments")
    if not isinstance(output_commitments, Mapping):
        raise ScreeningUnionPolicyRebindError(
            "source union run card lacks owned-output commitments"
        )
    typed_output_commitments = cast(Mapping[str, object], output_commitments)
    for key in (
        "owned_raw_artifacts",
        "owned_raw_observations",
        "owned_terminal_observations",
    ):
        if typed_output_commitments.get(key) != stage_commitments.get(key):
            raise ScreeningUnionPolicyRebindError(
                f"source union run-card {key} commitment mismatch"
            )


def _verify_allowed_policy_delta(
    *,
    source_policy: Mapping[str, object],
    target_policy: Mapping[str, object],
    source_manifest: Mapping[str, Any],
) -> Mapping[str, object]:
    if source_policy.get("schema_version") != target_policy.get("schema_version"):
        raise ScreeningUnionPolicyRebindError("cycle policy schema changed")
    if source_policy.get("eligibility_anchor") != target_policy.get(
        "eligibility_anchor"
    ):
        raise ScreeningUnionPolicyRebindError("cycle eligibility anchor changed")
    source_hashes_value = source_policy.get("screening_source_sha256")
    target_hashes_value = target_policy.get("screening_source_sha256")
    if not isinstance(source_hashes_value, Mapping) or not isinstance(
        target_hashes_value, Mapping
    ):
        raise ScreeningUnionPolicyRebindError(
            "cycle screening-source commitments are invalid"
        )
    source_hashes = dict(cast(Mapping[str, object], source_hashes_value))
    target_hashes = dict(cast(Mapping[str, object], target_hashes_value))
    if set(source_hashes) != set(target_hashes):
        raise ScreeningUnionPolicyRebindError("cycle screening-source key set changed")
    changed = {
        key: (source_hashes[key], target_hashes[key])
        for key in source_hashes
        if source_hashes[key] != target_hashes[key]
    }
    expected = {
        "restricted_material": (
            SOURCE_RESTRICTED_MATERIAL_SHA256,
            TARGET_RESTRICTED_MATERIAL_SHA256,
        )
    }
    if changed != expected:
        raise ScreeningUnionPolicyRebindError(
            "cycle policy differs outside the one audited restricted-material delta"
        )
    current_hashes = cast(
        Mapping[str, object],
        firecrawl_screening_implementation()["source_sha256"],
    )
    if (
        target_hashes["restricted_material"]
        != current_hashes["legalforecast/ingestion/restricted_material.py"]
    ):
        raise ScreeningUnionPolicyRebindError(
            "target policy does not match the current restricted-material source"
        )
    stage_commitments = cast(Mapping[str, object], source_manifest["stage_commitments"])
    implementation = cast(
        Mapping[str, object],
        stage_commitments["firecrawl_screening_implementation"],
    )
    implementation_hashes = cast(Mapping[str, object], implementation["source_sha256"])
    if (
        implementation_hashes["legalforecast/ingestion/restricted_material.py"]
        != TARGET_RESTRICTED_MATERIAL_SHA256
    ):
        raise ScreeningUnionPolicyRebindError(
            "source union was not produced under the target restricted-material "
            "implementation"
        )
    return {
        "name": POLICY_DELTA_NAME,
        "source_key": "restricted_material",
        "source_sha256": SOURCE_RESTRICTED_MATERIAL_SHA256,
        "target_sha256": TARGET_RESTRICTED_MATERIAL_SHA256,
        "semantic_direction": "strict_false_positive_suppression_only",
    }


def _policy_anchor(policy: Mapping[str, object]) -> date:
    value = policy.get("eligibility_anchor")
    if not isinstance(value, str):
        raise ScreeningUnionPolicyRebindError(
            "target cycle policy lacks an eligibility anchor"
        )
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ScreeningUnionPolicyRebindError(
            "target cycle eligibility anchor is invalid"
        ) from exc


def _evidence_date(evidence: Mapping[str, Any], field: str, candidate_id: str) -> date:
    value = evidence.get(field)
    if not isinstance(value, str):
        raise ScreeningUnionPolicyRebindError(f"{candidate_id} lacks {field}")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ScreeningUnionPolicyRebindError(
            f"{candidate_id} has invalid {field}"
        ) from exc


def _validate_candidate_id(candidate_id: str) -> None:
    if _CANDIDATE_ID.fullmatch(candidate_id) is None:
        raise ScreeningUnionPolicyRebindError(
            f"invalid CourtListener candidate ID: {candidate_id!r}"
        )


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode()
    ).hexdigest()


def _require_sha256(value: str, label: str) -> None:
    if _SHA256.fullmatch(value) is None:
        raise ScreeningUnionPolicyRebindError(f"{label} must be one lowercase SHA-256")


def _require_path_component(value: str, label: str) -> None:
    if (
        not value
        or value in {".", ".."}
        or Path(value).name != value
        or "/" in value
        or "\\" in value
    ):
        raise ScreeningUnionPolicyRebindError(
            f"{label} must be one safe path component"
        )


def _read_regular_file(path: Path, label: str) -> bytes:
    absolute = Path(os.path.abspath(path))
    canonical = path.resolve(strict=False)
    if absolute != canonical:
        raise ScreeningUnionPolicyRebindError(
            f"{label} must not traverse symlinks: {absolute}"
        )
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(canonical, flags)
    except OSError as exc:
        raise ScreeningUnionPolicyRebindError(
            f"{label} is unavailable: {canonical}"
        ) from exc
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise ScreeningUnionPolicyRebindError(
                f"{label} must be one singly linked regular file: {canonical}"
            )
        with os.fdopen(fd, "rb", closefd=True) as handle:
            fd = -1
            return handle.read()
    finally:
        if fd >= 0:
            os.close(fd)


def _safe_regular_file(path: Path, label: str) -> Path:
    canonical = _safe_output_path(path, label)
    _read_regular_file(path, label)
    return canonical


def _safe_directory(path: Path, label: str) -> Path:
    canonical = _safe_output_path(path, label)
    try:
        metadata = canonical.lstat()
    except OSError as exc:
        raise ScreeningUnionPolicyRebindError(
            f"{label} is unavailable: {canonical}"
        ) from exc
    if not stat.S_ISDIR(metadata.st_mode):
        raise ScreeningUnionPolicyRebindError(
            f"{label} must be a non-symlink directory: {canonical}"
        )
    return canonical


def _ensure_directory(path: Path, label: str) -> Path:
    canonical = _safe_output_path(path, label)
    if canonical.exists() and not canonical.is_dir():
        raise ScreeningUnionPolicyRebindError(
            f"{label} must be a non-symlink directory: {canonical}"
        )
    canonical.mkdir(parents=True, exist_ok=True)
    return _safe_directory(canonical, label)


def _safe_output_path(path: Path, label: str) -> Path:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        current /= component
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ScreeningUnionPolicyRebindError(
                f"{label} path cannot be inspected: {current}"
            ) from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise ScreeningUnionPolicyRebindError(
                f"{label} must not traverse symlinks: {current}"
            )
    return absolute


def _verify_disjoint_paths(
    *,
    immutable_inputs: tuple[Path, ...],
    target_cycle_store: Path,
    owned_outputs: tuple[Path, ...],
) -> None:
    for immutable in immutable_inputs:
        if _paths_overlap(immutable, target_cycle_store):
            raise ScreeningUnionPolicyRebindError(
                "target cycle store overlaps an immutable source input"
            )
    for index, output in enumerate(owned_outputs):
        for other in owned_outputs[index + 1 :]:
            if _paths_overlap(output, other):
                raise ScreeningUnionPolicyRebindError(
                    "policy-rebind owned output paths overlap"
                )
        for protected in (*immutable_inputs, target_cycle_store):
            if _paths_overlap(output, protected):
                raise ScreeningUnionPolicyRebindError(
                    "policy-rebind owned output overlaps a source or cycle store"
                )


def _paths_overlap(first: Path, second: Path) -> bool:
    return first == second or first in second.parents or second in first.parents


def _verify_owned_raw_tree(root: Path, *, expected_paths: set[Path]) -> None:
    actual_paths: set[Path] = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ScreeningUnionPolicyRebindError(
                f"raw artifact output contains a symlink: {path}"
            )
        if path.is_file():
            if path.stat().st_nlink != 1:
                raise ScreeningUnionPolicyRebindError(
                    f"raw artifact output contains a hardlinked file: {path}"
                )
            actual_paths.add(path.resolve())
        elif not path.is_dir():
            raise ScreeningUnionPolicyRebindError(
                f"raw artifact output contains an unsupported node: {path}"
            )
    if actual_paths != expected_paths:
        raise ScreeningUnionPolicyRebindError(
            "raw artifact output does not exactly reconcile to source commitments"
        )


def _json_object(payload: bytes, label: str) -> Mapping[str, Any]:
    try:
        value = json.loads(payload)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ScreeningUnionPolicyRebindError(f"{label} is invalid JSON") from exc
    if not isinstance(value, Mapping):
        raise ScreeningUnionPolicyRebindError(f"{label} must contain one object")
    return cast(Mapping[str, Any], value)


def _write_new_json(path: Path, value: Mapping[str, object]) -> str:
    payload = (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        + "\n"
    ).encode()
    if path.exists():
        existing = _read_regular_file(path, "target run card")
        if existing != payload:
            raise ScreeningUnionPolicyRebindError(
                f"target run card exists with different content: {path}"
            )
        return hashlib.sha256(existing).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(path, flags, 0o600)
    except OSError as exc:
        raise ScreeningUnionPolicyRebindError(
            f"target run card cannot be created: {path}"
        ) from exc
    with os.fdopen(fd, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    return hashlib.sha256(payload).hexdigest()
