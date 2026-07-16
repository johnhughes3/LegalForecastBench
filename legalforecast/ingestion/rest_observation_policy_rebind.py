"""Provider-free rebind of one authenticated terminal REST observation set."""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import sqlite3
import stat
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from types import MappingProxyType
from typing import Self, cast

from legalforecast.ingestion.courtlistener_acquisition import (
    screen_courtlistener_docket_page,
)
from legalforecast.ingestion.cycle_acquisition_store import (
    CycleAcquisitionStore,
    CycleAcquisitionStoreError,
    SnapshotVerificationError,
    verify_snapshot,
)

_CONTRACT_SCHEMA = "legalforecast.rest_observation_policy_rebind_contract.v1"
_RUN_CARD_SCHEMA = "legalforecast.rest_observation_policy_rebind_run.v1"
_OFFICIAL_CONTRACT_SHA256 = (
    "c257d1b9233b81c631c67a68041bf2285feb5a8a7a880a3059e3f7c4d912c85b"
)
_SNAPSHOT_FILES = (
    "screened-cases.jsonl",
    "exclusions.jsonl",
    "summary.json",
    "candidates.jsonl",
    "observations.jsonl",
    "raw-artifacts.jsonl",
)
_TERMINAL_STATES = frozenset({"accepted", "excluded", "skipped_immutable"})
_SHA256_LENGTH = 64


class RestObservationPolicyRebindError(ValueError):
    """Raised when rebind provenance is incomplete, changed, or contradictory."""


@dataclass(frozen=True, slots=True)
class _SourceStoreEvidence:
    """Authenticated source metadata read without opening the store read-write."""

    cycle_hash: str
    cycle_policy: Mapping[str, object]
    batch_digest: str
    candidate_ids: frozenset[str]


@dataclass(frozen=True, slots=True)
class RestObservationRebindContract:
    """Immutable allowlist for the one authorized screening-policy rebind."""

    schema_version: str
    source_cycle_hash: str
    target_cycle_hash: str
    source_batch_id: str
    source_snapshot_manifest_sha256: str
    selection_run_card_sha256: str
    selected_candidate_set_sha256: str
    selected_candidate_count: int
    novel_candidate_count: int
    novel_candidate_ids_sha256: str
    novel_outcomes_sha256: str
    source_policy: Mapping[str, object]
    target_policy: Mapping[str, object]
    allowed_policy_delta: Mapping[str, object]
    semantic_noop_proof: Mapping[str, object]
    novel_outcomes: tuple[Mapping[str, str], ...]

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> Self:
        """Parse a contract without weakening its exact field requirements."""

        required = {
            "schema_version",
            "source_cycle_hash",
            "target_cycle_hash",
            "source_batch_id",
            "source_snapshot_manifest_sha256",
            "selection_run_card_sha256",
            "selected_candidate_set_sha256",
            "selected_candidate_count",
            "novel_candidate_count",
            "novel_candidate_ids_sha256",
            "novel_outcomes_sha256",
            "source_policy",
            "target_policy",
            "allowed_policy_delta",
            "semantic_noop_proof",
            "novel_outcomes",
        }
        if set(value) != required:
            raise RestObservationPolicyRebindError(
                "rebind contract field set is not exact"
            )
        outcomes_value = value["novel_outcomes"]
        if not isinstance(outcomes_value, list):
            raise RestObservationPolicyRebindError(
                "rebind contract novel_outcomes must be a list"
            )
        outcomes: list[Mapping[str, str]] = []
        for row in cast(list[object], outcomes_value):
            if not isinstance(row, Mapping):
                raise RestObservationPolicyRebindError(
                    "rebind contract contains an invalid novel outcome"
                )
            typed_outcome = cast(Mapping[str, object], row)
            if set(typed_outcome) != {
                "candidate_id",
                "state",
                "reason_code",
                "source_observation_sha256",
            }:
                raise RestObservationPolicyRebindError(
                    "rebind contract contains an invalid novel outcome"
                )
            outcomes.append(
                MappingProxyType(
                    {
                        key: _required_text(typed_outcome, key)
                        for key in (
                            "candidate_id",
                            "state",
                            "reason_code",
                            "source_observation_sha256",
                        )
                    }
                )
            )
        source_policy = _required_mapping(value, "source_policy")
        target_policy = _required_mapping(value, "target_policy")
        allowed_delta = _required_mapping(value, "allowed_policy_delta")
        semantic_proof = _required_mapping(value, "semantic_noop_proof")
        contract = cls(
            schema_version=_required_text(value, "schema_version"),
            source_cycle_hash=_required_text(value, "source_cycle_hash"),
            target_cycle_hash=_required_text(value, "target_cycle_hash"),
            source_batch_id=_required_text(value, "source_batch_id"),
            source_snapshot_manifest_sha256=_required_text(
                value, "source_snapshot_manifest_sha256"
            ),
            selection_run_card_sha256=_required_text(
                value, "selection_run_card_sha256"
            ),
            selected_candidate_set_sha256=_required_text(
                value, "selected_candidate_set_sha256"
            ),
            selected_candidate_count=_required_int(value, "selected_candidate_count"),
            novel_candidate_count=_required_int(value, "novel_candidate_count"),
            novel_candidate_ids_sha256=_required_text(
                value, "novel_candidate_ids_sha256"
            ),
            novel_outcomes_sha256=_required_text(value, "novel_outcomes_sha256"),
            source_policy=MappingProxyType(dict(source_policy)),
            target_policy=MappingProxyType(dict(target_policy)),
            allowed_policy_delta=MappingProxyType(dict(allowed_delta)),
            semantic_noop_proof=MappingProxyType(dict(semantic_proof)),
            novel_outcomes=tuple(outcomes),
        )
        contract.validate()
        return contract

    def replace(self, **changes: object) -> Self:
        """Return a modified contract for focused tests and review tooling."""

        return replace(self, **changes)

    def validate(self) -> None:
        """Fail closed unless every internal commitment reconciles."""

        if self.schema_version != _CONTRACT_SCHEMA:
            raise RestObservationPolicyRebindError(
                "rebind contract schema version mismatch"
            )
        for label, digest in (
            ("source cycle hash", self.source_cycle_hash),
            ("target cycle hash", self.target_cycle_hash),
            ("source snapshot manifest SHA-256", self.source_snapshot_manifest_sha256),
            ("selection run-card SHA-256", self.selection_run_card_sha256),
            ("selected candidate set SHA-256", self.selected_candidate_set_sha256),
            ("novel candidate IDs SHA-256", self.novel_candidate_ids_sha256),
            ("novel outcomes SHA-256", self.novel_outcomes_sha256),
        ):
            _require_sha256(digest, label)
        if self.selected_candidate_count < 1 or self.novel_candidate_count < 1:
            raise RestObservationPolicyRebindError(
                "rebind contract counts must be positive"
            )
        if len(self.novel_outcomes) != self.novel_candidate_count:
            raise RestObservationPolicyRebindError(
                "rebind contract novel outcome count mismatch"
            )
        candidate_ids = [row["candidate_id"] for row in self.novel_outcomes]
        if candidate_ids != sorted(candidate_ids) or len(set(candidate_ids)) != len(
            candidate_ids
        ):
            raise RestObservationPolicyRebindError(
                "rebind contract novel candidate IDs are not unique and sorted"
            )
        for row in self.novel_outcomes:
            if row["state"] not in _TERMINAL_STATES:
                raise RestObservationPolicyRebindError(
                    "rebind contract contains a nonterminal outcome"
                )
            _require_sha256(
                row["source_observation_sha256"], "source observation SHA-256"
            )
        if _canonical_sha256(candidate_ids) != self.novel_candidate_ids_sha256:
            raise RestObservationPolicyRebindError(
                "rebind contract novel candidate ID commitment mismatch"
            )
        if (
            _canonical_sha256([dict(row) for row in self.novel_outcomes])
            != self.novel_outcomes_sha256
        ):
            raise RestObservationPolicyRebindError(
                "rebind contract novel outcome commitment mismatch"
            )
        _validate_policy_delta(self)


@dataclass(frozen=True, slots=True)
class RestObservationPolicyRebindResult:
    """Published provider-free rebind evidence."""

    rebound_count: int
    accepted_count: int
    excluded_count: int
    snapshot_path: Path
    snapshot_manifest_sha256: str
    run_card_path: Path
    run_card_sha256: str
    provider_activity_executed: bool = False
    paid_activity_executed: bool = False


def load_official_rest_observation_rebind_contract() -> RestObservationRebindContract:
    """Load the repository-pinned exact 100-outcome authorization."""

    path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "rest_observation_policy_rebind_v1.json"
    )
    payload = _read_regular_file(path, label="official rebind contract")
    digest = hashlib.sha256(payload).hexdigest()
    if digest != _OFFICIAL_CONTRACT_SHA256:
        raise RestObservationPolicyRebindError(
            "official rebind contract SHA-256 mismatch"
        )
    record = _parse_json_object(payload, label="official rebind contract")
    return RestObservationRebindContract.from_mapping(record)


def verify_official_rest_observation_rebind_semantics() -> Mapping[str, object]:
    """Verify the pinned code-diff proof without reading any provider state."""

    contract = load_official_rest_observation_rebind_contract()
    _verify_git_noop_semantics(contract)
    return dict(contract.semantic_noop_proof)


def rebind_terminal_rest_observations(
    *,
    source_store_path: str | Path,
    source_snapshot_path: str | Path,
    selection_run_card_path: str | Path,
    target_store_path: str | Path,
    target_batch_id: str,
    snapshot_output_root: str | Path,
    snapshot_id: str,
    run_card_path: str | Path,
    contract: RestObservationRebindContract | None = None,
    verify_git_semantics: bool = True,
) -> RestObservationPolicyRebindResult:
    """Rebind exactly the authorized terminal REST outcomes without providers."""

    active_contract = contract or load_official_rest_observation_rebind_contract()
    active_contract.validate()
    if verify_git_semantics:
        _verify_git_noop_semantics(active_contract)

    source_snapshot = Path(source_snapshot_path).resolve()
    selection_path = Path(selection_run_card_path).resolve()
    source_payloads, source_manifest, source_manifest_sha256 = _buffer_snapshot(
        source_snapshot,
        expected_manifest_sha256=active_contract.source_snapshot_manifest_sha256,
    )
    selection_payload = _read_regular_file(selection_path, label="selection run card")
    if hashlib.sha256(selection_payload).hexdigest() != (
        active_contract.selection_run_card_sha256
    ):
        raise RestObservationPolicyRebindError("selection run-card SHA-256 mismatch")
    selection = _parse_json_object(selection_payload, label="selection run card")
    selected_ids = _selected_candidate_ids(selection, active_contract)

    source_evidence = _read_source_store_evidence(
        source_store_path,
        batch_id=active_contract.source_batch_id,
        snapshot_path=source_snapshot,
        snapshot_manifest=source_manifest,
    )
    if source_evidence.cycle_hash != active_contract.source_cycle_hash:
        raise RestObservationPolicyRebindError("source store cycle hash mismatch")
    if dict(source_evidence.cycle_policy) != dict(active_contract.source_policy):
        raise RestObservationPolicyRebindError("source store policy mismatch")
    if source_evidence.candidate_ids != frozenset(selected_ids):
        raise RestObservationPolicyRebindError(
            "source store candidate set does not match selected set"
        )

    _verify_buffered_snapshot(
        source_payloads,
        source_manifest,
        expected_cycle_hash=active_contract.source_cycle_hash,
        expected_batch_digest=source_evidence.batch_digest,
    )
    if source_manifest.get("batch_id") != active_contract.source_batch_id:
        raise RestObservationPolicyRebindError("source snapshot batch ID mismatch")

    source_candidate_ids = _candidate_ids_from_payload(
        source_payloads["candidates.jsonl"]
    )
    if source_candidate_ids != set(selected_ids):
        raise RestObservationPolicyRebindError(
            "source snapshot candidate set does not match selected set"
        )
    source_observations = _terminal_observations(
        source_payloads["observations.jsonl"], source_candidate_ids
    )
    pinned = _authenticate_pinned_outcomes(active_contract, source_observations)
    raw_candidate_ids = _candidate_ids_from_payload(
        source_payloads["raw-artifacts.jsonl"], allow_empty=True
    )
    if raw_candidate_ids.intersection(pinned):
        raise RestObservationPolicyRebindError(
            "pinned REST outcomes unexpectedly depend on raw artifacts"
        )

    run_card_target = Path(run_card_path).resolve()
    snapshot_root = Path(snapshot_output_root).resolve()
    if run_card_target.exists():
        raise RestObservationPolicyRebindError(
            f"rebind run card already exists: {run_card_target}"
        )

    try:
        with CycleAcquisitionStore(target_store_path) as target_store:
            if target_store.cycle_hash != active_contract.target_cycle_hash:
                raise RestObservationPolicyRebindError(
                    "target store cycle hash mismatch"
                )
            if dict(target_store.cycle_policy) != dict(active_contract.target_policy):
                raise RestObservationPolicyRebindError("target store policy mismatch")
            target_candidate_ids = set(target_store.candidate_ids(target_batch_id))
            if target_candidate_ids != set(selected_ids):
                raise RestObservationPolicyRebindError(
                    "target batch candidate set does not match selected set"
                )
            batch_local = {
                row.candidate_id: row
                for row in target_store.batch_terminal_observations(target_batch_id)
                if row.candidate_id in pinned
            }
            for candidate_id, existing in batch_local.items():
                source_record = pinned[candidate_id]
                current = target_store.current_observation(candidate_id)
                if (
                    existing.state != source_record["state"]
                    or existing.reason_code != source_record["reason_code"]
                    or dict(existing.evidence) != source_record["evidence"]
                    or existing.observed_at != source_record["observed_at"]
                    or current is None
                    or current.observation_id != existing.observation_id
                ):
                    raise RestObservationPolicyRebindError(
                        f"target batch prior rebind drift for {candidate_id}"
                    )
            unresolved = {
                candidate_id
                for candidate_id in target_candidate_ids
                if target_store.current_observation(candidate_id) is None
            }
            expected_unresolved = set(pinned).difference(batch_local)
            if unresolved != expected_unresolved:
                raise RestObservationPolicyRebindError(
                    "target unresolved candidate set does not equal the pinned "
                    "novel set remaining after exact resume checkpoints"
                )
            for candidate_id in sorted(expected_unresolved):
                source_record = pinned[candidate_id]
                target_store.record_observation(
                    candidate_id,
                    batch_id=target_batch_id,
                    state=cast(str, source_record["state"]),
                    reason_code=cast(str, source_record["reason_code"]),
                    evidence=cast(Mapping[str, object], source_record["evidence"]),
                    observed_at=cast(str, source_record["observed_at"]),
                    audit_immutable_skip=False,
                )
            if not target_store.snapshot_is_saturated(target_batch_id):
                raise RestObservationPolicyRebindError(
                    "target batch is terminal but not saturated"
                )
            stage_commitments = {
                "stage": "rebind-terminal-rest-observations",
                "source_cycle_hash": active_contract.source_cycle_hash,
                "target_cycle_hash": active_contract.target_cycle_hash,
                "source_snapshot_manifest_sha256": source_manifest_sha256,
                "selection_run_card_sha256": (
                    active_contract.selection_run_card_sha256
                ),
                "selected_candidate_set_sha256": (
                    active_contract.selected_candidate_set_sha256
                ),
                "novel_candidate_count": active_contract.novel_candidate_count,
                "novel_candidate_ids_sha256": (
                    active_contract.novel_candidate_ids_sha256
                ),
                "novel_outcomes_sha256": active_contract.novel_outcomes_sha256,
                "provider_activity_requested": False,
                "provider_activity_executed": False,
                "paid_activity_requested": False,
                "paid_activity_executed": False,
            }
            existing_snapshot = target_store.existing_complete_snapshot_evidence(
                snapshot_root,
                snapshot_id=snapshot_id,
                batch_id=target_batch_id,
            )
            if existing_snapshot is None:
                snapshot_path = target_store.export_snapshot(
                    snapshot_root,
                    snapshot_id=snapshot_id,
                    batch_id=target_batch_id,
                    complete=True,
                    stage_commitments=stage_commitments,
                )
            else:
                if existing_snapshot.manifest.get("stage_commitments") != (
                    stage_commitments
                ):
                    raise RestObservationPolicyRebindError(
                        "existing rebind snapshot stage commitments drifted"
                    )
                snapshot_path = existing_snapshot.path
    except RestObservationPolicyRebindError:
        raise
    except (CycleAcquisitionStoreError, KeyError, OSError, ValueError) as exc:
        raise RestObservationPolicyRebindError(
            f"cannot publish current-policy rebind: {exc}"
        ) from exc

    snapshot_manifest_path = snapshot_path / "manifest.json"
    snapshot_manifest_sha256 = hashlib.sha256(
        _read_regular_file(snapshot_manifest_path, label="current snapshot manifest")
    ).hexdigest()
    accepted_count = sum(
        row["state"] == "accepted" for row in active_contract.novel_outcomes
    )
    excluded_count = active_contract.novel_candidate_count - accepted_count
    run_card = {
        "schema_version": _RUN_CARD_SCHEMA,
        "stage": "rebind-terminal-rest-observations",
        "source_store_path": str(Path(source_store_path).resolve()),
        "source_snapshot_path": str(source_snapshot),
        "source_snapshot_manifest_sha256": source_manifest_sha256,
        "selection_run_card_path": str(selection_path),
        "selection_run_card_sha256": active_contract.selection_run_card_sha256,
        "selected_candidate_set_sha256": (
            active_contract.selected_candidate_set_sha256
        ),
        "selected_candidate_count": active_contract.selected_candidate_count,
        "target_store_path": str(Path(target_store_path).resolve()),
        "target_batch_id": target_batch_id,
        "source_cycle_hash": active_contract.source_cycle_hash,
        "target_cycle_hash": active_contract.target_cycle_hash,
        "allowed_policy_delta": dict(active_contract.allowed_policy_delta),
        "semantic_noop_proof": dict(active_contract.semantic_noop_proof),
        "novel_candidate_count": active_contract.novel_candidate_count,
        "novel_candidate_ids": sorted(pinned),
        "novel_candidate_ids_sha256": active_contract.novel_candidate_ids_sha256,
        "novel_outcomes": [dict(row) for row in active_contract.novel_outcomes],
        "novel_outcomes_sha256": active_contract.novel_outcomes_sha256,
        "accepted_count": accepted_count,
        "excluded_count": excluded_count,
        "snapshot_path": str(snapshot_path),
        "snapshot_manifest_sha256": snapshot_manifest_sha256,
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "pacer_fee_acknowledgment_requested": False,
        "pacer_fee_acknowledgment_executed": False,
    }
    run_card_sha256 = _atomic_write_json(run_card_target, run_card)
    return RestObservationPolicyRebindResult(
        rebound_count=active_contract.novel_candidate_count,
        accepted_count=accepted_count,
        excluded_count=excluded_count,
        snapshot_path=snapshot_path,
        snapshot_manifest_sha256=snapshot_manifest_sha256,
        run_card_path=run_card_target,
        run_card_sha256=run_card_sha256,
    )


def _validate_policy_delta(contract: RestObservationRebindContract) -> None:
    source = dict(contract.source_policy)
    target = dict(contract.target_policy)
    source_hashes = _required_mapping(source, "screening_source_sha256")
    target_hashes = _required_mapping(target, "screening_source_sha256")
    source_without_hashes = {
        k: v for k, v in source.items() if k != "screening_source_sha256"
    }
    target_without_hashes = {
        k: v for k, v in target.items() if k != "screening_source_sha256"
    }
    changed_keys = sorted(
        key
        for key in set(source_hashes) | set(target_hashes)
        if source_hashes.get(key) != target_hashes.get(key)
    )
    expected_key = _required_text(contract.allowed_policy_delta, "source_key")
    if source_without_hashes != target_without_hashes or changed_keys != [expected_key]:
        raise RestObservationPolicyRebindError(
            "rebind policy must contain exactly one screening-source delta"
        )
    if source_hashes.get(expected_key) != contract.allowed_policy_delta.get(
        "old_sha256"
    ) or target_hashes.get(expected_key) != contract.allowed_policy_delta.get(
        "new_sha256"
    ):
        raise RestObservationPolicyRebindError(
            "rebind policy delta does not match the authenticated old/new hashes"
        )


def _verify_git_noop_semantics(contract: RestObservationRebindContract) -> None:
    proof = contract.semantic_noop_proof
    required = {
        "commit",
        "commit_screening_diff_sha256",
        "excluded_evidence_markers",
        "old_to_current_diff_shape",
        "old_to_current_diff_sha256",
        "rest_observation_mode",
        "screening_source_path",
        "source_code_commit",
        "target_code_commit",
    }
    if set(proof) != required:
        raise RestObservationPolicyRebindError(
            "semantic no-op proof field set is not exact"
        )
    if (
        proof.get("old_to_current_diff_shape")
        != ("candidate_text_override_optional_default_none")
        or proof.get("rest_observation_mode") != "candidate_text_override_none"
    ):
        raise RestObservationPolicyRebindError("semantic no-op proof mode mismatch")
    repository_root = Path(__file__).resolve().parents[2]
    source_path = _required_text(proof, "screening_source_path")
    if source_path != "legalforecast/ingestion/courtlistener_acquisition.py":
        raise RestObservationPolicyRebindError(
            "semantic no-op proof screening path mismatch"
        )
    old_commit = _required_text(proof, "source_code_commit")
    target_commit = _required_text(proof, "target_code_commit")
    delta_commit = _required_text(proof, "commit")
    old_bytes = _git_bytes(repository_root, "show", f"{old_commit}:{source_path}")
    target_bytes = _git_bytes(repository_root, "show", f"{target_commit}:{source_path}")
    if (
        hashlib.sha256(old_bytes).hexdigest()
        != (contract.allowed_policy_delta["old_sha256"])
        or hashlib.sha256(target_bytes).hexdigest()
        != (contract.allowed_policy_delta["new_sha256"])
    ):
        raise RestObservationPolicyRebindError(
            "semantic no-op proof code blobs do not match policy hashes"
        )
    current_bytes = _read_regular_file(
        repository_root / source_path, label="current screening source"
    )
    if (
        hashlib.sha256(current_bytes).hexdigest()
        != (contract.allowed_policy_delta["new_sha256"])
    ):
        raise RestObservationPolicyRebindError(
            "current screening source does not match authorized target hash"
        )
    old_to_current = _git_bytes(
        repository_root,
        "diff",
        old_commit,
        target_commit,
        "--",
        source_path,
    )
    if hashlib.sha256(old_to_current).hexdigest() != proof.get(
        "old_to_current_diff_sha256"
    ):
        raise RestObservationPolicyRebindError(
            "old-to-current screening diff commitment mismatch"
        )
    commit_diff = _git_bytes(
        repository_root,
        "diff",
        f"{delta_commit}^",
        delta_commit,
        "--",
        source_path,
    )
    if hashlib.sha256(commit_diff).hexdigest() != proof.get(
        "commit_screening_diff_sha256"
    ):
        raise RestObservationPolicyRebindError(
            "6ffbbdb screening diff commitment mismatch"
        )
    parameter = inspect.signature(screen_courtlistener_docket_page).parameters.get(
        "candidate_text_override"
    )
    if parameter is None or parameter.default is not None:
        raise RestObservationPolicyRebindError(
            "REST screen override is not optional with default None"
        )


def _git_bytes(repository_root: Path, *arguments: str) -> bytes:
    try:
        result = subprocess.run(
            ("git", *arguments),
            cwd=repository_root,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RestObservationPolicyRebindError(
            f"cannot verify semantic no-op proof with git: {exc}"
        ) from exc
    return result.stdout


def _buffer_snapshot(
    snapshot: Path,
    *,
    expected_manifest_sha256: str,
) -> tuple[Mapping[str, bytes], Mapping[str, object], str]:
    if snapshot.is_symlink() or not snapshot.is_dir():
        raise RestObservationPolicyRebindError(
            f"source snapshot is not a regular directory: {snapshot}"
        )
    manifest_bytes = _read_regular_file(
        snapshot / "manifest.json", label="source snapshot manifest"
    )
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    if manifest_sha256 != expected_manifest_sha256:
        raise RestObservationPolicyRebindError(
            "source snapshot manifest SHA-256 mismatch"
        )
    manifest = _parse_json_object(manifest_bytes, label="source snapshot manifest")
    payloads = {
        filename: _read_regular_file(
            snapshot / filename, label=f"source snapshot {filename}"
        )
        for filename in _SNAPSHOT_FILES
    }
    return MappingProxyType(payloads), MappingProxyType(manifest), manifest_sha256


def _read_source_store_evidence(
    store_path: str | Path,
    *,
    batch_id: str,
    snapshot_path: Path,
    snapshot_manifest: Mapping[str, object],
) -> _SourceStoreEvidence:
    """Read the immutable source store without schema setup or write locks."""

    source = Path(store_path).resolve()
    try:
        if not stat.S_ISREG(source.lstat().st_mode):
            raise RestObservationPolicyRebindError(
                f"source store is not a regular file: {source}"
            )
        connection = sqlite3.connect(
            f"{source.as_uri()}?mode=ro",
            uri=True,
        )
        connection.row_factory = sqlite3.Row
        try:
            cycle_row = connection.execute(
                """
                SELECT policy_json, policy_hash
                FROM cycle_identity
                WHERE singleton = 1
                """
            ).fetchone()
            if cycle_row is None:
                raise RestObservationPolicyRebindError(
                    "source store has no cycle identity"
                )
            cycle_policy = _parse_json_object(
                str(cycle_row["policy_json"]).encode(),
                label="source store cycle policy",
            )
            cycle_hash = str(cycle_row["policy_hash"])

            batch_row = connection.execute(
                """
                SELECT cycle_hash, config_digest
                FROM batches
                WHERE batch_id = ?
                """,
                (batch_id,),
            ).fetchone()
            if batch_row is None:
                raise RestObservationPolicyRebindError(
                    f"source store has no batch {batch_id!r}"
                )
            if str(batch_row["cycle_hash"]) != cycle_hash:
                raise RestObservationPolicyRebindError(
                    "source batch cycle hash does not match source store"
                )

            candidate_ids = frozenset(
                str(row["candidate_id"])
                for row in connection.execute(
                    """
                    SELECT DISTINCT candidate_id
                    FROM discovery_hits
                    WHERE batch_id = ?
                    """,
                    (batch_id,),
                )
            )

            snapshot_id = _required_text(snapshot_manifest, "snapshot_id")
            snapshot_row = connection.execute(
                """
                SELECT batch_id, complete, path, manifest_json
                FROM snapshots
                WHERE snapshot_id = ?
                """,
                (snapshot_id,),
            ).fetchone()
            if snapshot_row is None:
                raise RestObservationPolicyRebindError(
                    "source snapshot is not registered in source store"
                )
            registered_manifest = _parse_json_object(
                str(snapshot_row["manifest_json"]).encode(),
                label="registered source snapshot manifest",
            )
            if (
                str(snapshot_row["batch_id"]) != batch_id
                or int(snapshot_row["complete"]) != 1
                or Path(str(snapshot_row["path"])).resolve() != snapshot_path
                or registered_manifest != dict(snapshot_manifest)
            ):
                raise RestObservationPolicyRebindError(
                    "source snapshot registration does not match supplied snapshot"
                )
        finally:
            connection.close()
    except RestObservationPolicyRebindError:
        raise
    except (OSError, sqlite3.Error, UnicodeError, ValueError) as exc:
        raise RestObservationPolicyRebindError(
            f"cannot authenticate source store: {exc}"
        ) from exc

    return _SourceStoreEvidence(
        cycle_hash=cycle_hash,
        cycle_policy=MappingProxyType(cycle_policy),
        batch_digest=str(batch_row["config_digest"]),
        candidate_ids=candidate_ids,
    )


def _verify_buffered_snapshot(
    payloads: Mapping[str, bytes],
    manifest: Mapping[str, object],
    *,
    expected_cycle_hash: str,
    expected_batch_digest: str,
) -> None:
    try:
        with tempfile.TemporaryDirectory(prefix="legalforecast-rest-rebind-") as root:
            private = Path(root) / "snapshot"
            private.mkdir()
            (private / "manifest.json").write_bytes(
                _canonical_json_bytes(manifest) + b"\n"
            )
            for filename, payload in payloads.items():
                (private / filename).write_bytes(payload)
            verified = verify_snapshot(
                private,
                expected_cycle_hash=expected_cycle_hash,
                expected_batch_digest=expected_batch_digest,
                require_complete=True,
                require_saturated=True,
            )
    except (OSError, SnapshotVerificationError) as exc:
        raise RestObservationPolicyRebindError(
            f"source snapshot verification failed: {exc}"
        ) from exc
    if dict(verified) != dict(manifest):
        raise RestObservationPolicyRebindError(
            "source snapshot manifest changed during private verification"
        )


def _selected_candidate_ids(
    selection: Mapping[str, object],
    contract: RestObservationRebindContract,
) -> tuple[str, ...]:
    if selection.get("selected_candidate_set_sha256") != (
        contract.selected_candidate_set_sha256
    ):
        raise RestObservationPolicyRebindError(
            "selected candidate set commitment mismatch"
        )
    if selection.get("leads_selected") != contract.selected_candidate_count:
        raise RestObservationPolicyRebindError("selected candidate count mismatch")
    for field in (
        "provider_activity_requested",
        "provider_activity_executed",
        "paid_activity_requested",
        "paid_activity_executed",
    ):
        if selection.get(field) is not False:
            raise RestObservationPolicyRebindError(
                f"selection run card does not prove {field}=false"
            )
    selected = selection.get("selected")
    if not isinstance(selected, list):
        raise RestObservationPolicyRebindError(
            "selection run card selected list mismatch"
        )
    selected_rows = cast(list[object], selected)
    if len(selected_rows) != contract.selected_candidate_count:
        raise RestObservationPolicyRebindError(
            "selection run card selected list mismatch"
        )
    candidate_ids: list[str] = []
    ranks: list[int] = []
    for row in selected_rows:
        if not isinstance(row, Mapping):
            raise RestObservationPolicyRebindError(
                "selection run card contains a non-object selected row"
            )
        typed_row = cast(Mapping[str, object], row)
        docket_id = _required_text(typed_row, "docket_id")
        rank = typed_row.get("rank")
        if not isinstance(rank, int) or isinstance(rank, bool):
            raise RestObservationPolicyRebindError(
                "selection run card contains an invalid rank"
            )
        candidate_ids.append(f"courtlistener-docket-{docket_id}")
        ranks.append(rank)
    if ranks != list(range(1, len(selected_rows) + 1)):
        raise RestObservationPolicyRebindError(
            "selection run card ranks are not contiguous"
        )
    if len(set(candidate_ids)) != len(candidate_ids):
        raise RestObservationPolicyRebindError(
            "selection run card contains duplicate candidate IDs"
        )
    return tuple(candidate_ids)


def _terminal_observations(
    payload: bytes,
    candidate_ids: set[str],
) -> Mapping[str, Mapping[str, object]]:
    observations: dict[str, Mapping[str, object]] = {}
    for row in _read_jsonl(payload, label="source observations"):
        candidate_id = _required_text(row, "candidate_id")
        if candidate_id in observations:
            raise RestObservationPolicyRebindError(
                f"source snapshot has multiple observations for {candidate_id}"
            )
        if row.get("state") not in _TERMINAL_STATES:
            raise RestObservationPolicyRebindError(
                f"source snapshot has a nonterminal observation for {candidate_id}"
            )
        observations[candidate_id] = MappingProxyType(dict(row))
    if set(observations) != candidate_ids:
        raise RestObservationPolicyRebindError(
            "source snapshot does not have exactly one terminal observation "
            "per candidate"
        )
    return MappingProxyType(observations)


def _authenticate_pinned_outcomes(
    contract: RestObservationRebindContract,
    observations: Mapping[str, Mapping[str, object]],
) -> Mapping[str, Mapping[str, object]]:
    markers = contract.semantic_noop_proof.get("excluded_evidence_markers")
    if not isinstance(markers, list) or not all(
        isinstance(marker, str) and marker for marker in cast(list[object], markers)
    ):
        raise RestObservationPolicyRebindError(
            "semantic no-op proof evidence markers are invalid"
        )
    typed_markers = cast(list[str], markers)
    pinned: dict[str, Mapping[str, object]] = {}
    for commitment in contract.novel_outcomes:
        candidate_id = commitment["candidate_id"]
        source = observations.get(candidate_id)
        if source is None:
            raise RestObservationPolicyRebindError(
                f"missing pinned source outcome for {candidate_id}"
            )
        if (
            source.get("state") != commitment["state"]
            or source.get("reason_code") != commitment["reason_code"]
            or _canonical_sha256(source) != commitment["source_observation_sha256"]
        ):
            raise RestObservationPolicyRebindError(
                f"pinned source outcome mismatch for {candidate_id}"
            )
        evidence = source.get("evidence")
        if not isinstance(evidence, Mapping):
            raise RestObservationPolicyRebindError(
                f"source outcome evidence is invalid for {candidate_id}"
            )
        typed_evidence = cast(Mapping[str, object], evidence)
        if typed_evidence.get("provider") != "courtlistener-recap-rest-v4":
            raise RestObservationPolicyRebindError(
                "source outcome is not a CourtListener REST observation: "
                f"{candidate_id}"
            )
        evidence_text = json.dumps(
            _plain_json(typed_evidence), sort_keys=True
        ).casefold()
        if any(marker.casefold() in evidence_text for marker in typed_markers):
            raise RestObservationPolicyRebindError(
                "source outcome used a non-default candidate-text override: "
                f"{candidate_id}"
            )
        pinned[candidate_id] = source
    return MappingProxyType(pinned)


def _candidate_ids_from_payload(
    payload: bytes,
    *,
    allow_empty: bool = False,
) -> set[str]:
    rows = _read_jsonl(payload, label="snapshot candidate-linked payload")
    candidate_ids = {_required_text(row, "candidate_id") for row in rows}
    if not allow_empty and len(candidate_ids) != len(rows):
        raise RestObservationPolicyRebindError(
            "snapshot candidate payload contains duplicate IDs"
        )
    return candidate_ids


def _read_jsonl(payload: bytes, *, label: str) -> tuple[dict[str, object], ...]:
    try:
        lines = payload.decode("utf-8").splitlines()
    except UnicodeError as exc:
        raise RestObservationPolicyRebindError(f"cannot decode {label}") from exc
    records: list[dict[str, object]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            parsed: object = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RestObservationPolicyRebindError(
                f"invalid {label} JSON at line {line_number}"
            ) from exc
        if not isinstance(parsed, dict):
            raise RestObservationPolicyRebindError(
                f"{label} line {line_number} is not an object"
            )
        records.append(cast(dict[str, object], parsed))
    return tuple(records)


def _read_regular_file(path: Path, *, label: str) -> bytes:
    try:
        if not stat.S_ISREG(path.lstat().st_mode):
            raise RestObservationPolicyRebindError(
                f"{label} is not a regular file: {path}"
            )
        return path.read_bytes()
    except OSError as exc:
        raise RestObservationPolicyRebindError(
            f"cannot read {label}: {path}: {exc}"
        ) from exc


def _parse_json_object(payload: bytes, *, label: str) -> dict[str, object]:
    try:
        parsed: object = json.loads(payload)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RestObservationPolicyRebindError(f"invalid {label} JSON") from exc
    if not isinstance(parsed, dict):
        raise RestObservationPolicyRebindError(f"{label} must be a JSON object")
    return cast(dict[str, object], parsed)


def _atomic_write_json(path: Path, record: Mapping[str, object]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _canonical_json_bytes(record) + b"\n"
    temporary = path.parent / f".{path.name}.{os.getpid()}.tmp"
    try:
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
        temporary.unlink()
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return hashlib.sha256(payload).hexdigest()


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        _plain_json(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode()


def _plain_json(value: object) -> object:
    if isinstance(value, Mapping):
        typed_mapping = cast(Mapping[object, object], value)
        return {str(key): _plain_json(nested) for key, nested in typed_mapping.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_plain_json(nested) for nested in cast(Sequence[object], value)]
    return value


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _required_mapping(value: Mapping[str, object], key: str) -> Mapping[str, object]:
    nested = value.get(key)
    if not isinstance(nested, Mapping):
        raise RestObservationPolicyRebindError(f"{key} must be a JSON object")
    return cast(Mapping[str, object], nested)


def _required_text(value: Mapping[str, object], key: str) -> str:
    text = value.get(key)
    if not isinstance(text, str) or not text.strip():
        raise RestObservationPolicyRebindError(f"{key} must be non-empty text")
    return text


def _required_int(value: Mapping[str, object], key: str) -> int:
    number = value.get(key)
    if not isinstance(number, int) or isinstance(number, bool):
        raise RestObservationPolicyRebindError(f"{key} must be an integer")
    return number


def _require_sha256(value: str, label: str) -> None:
    if len(value) != _SHA256_LENGTH or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise RestObservationPolicyRebindError(f"{label} is not lowercase SHA-256")
