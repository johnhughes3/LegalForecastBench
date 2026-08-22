"""Provider-free issuer for the authenticated Cycle 1 execution decisions.

The execution-policy generator already validates the policy shape.  This module
owns the missing upstream step: derive the decisions from authenticated
manifest, forecast, registry, caps, labeling/cohort, observation, and Beads
evidence, then create-only publish both the decisions and the generated policy.
No policy value is accepted from an operator on the command line.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import sqlite3
import subprocess
from collections.abc import Callable, Mapping
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Final, cast

from legalforecast.contracts.schemas import (
    MANIFEST_EXECUTION_DECISIONS_BEADS_OBSERVATION_V2,
    MANIFEST_EXECUTION_DECISIONS_RUN_CARD_V2,
    MANIFEST_EXECUTION_DECISIONS_V2,
    MANIFEST_MODE_FORECAST_RUN_RECORD_V1,
    NO_BASELINES_V1,
)
from legalforecast.evals.corpus_manifest.beads_observation import (
    CONTAMINATION_LINE as _CONTAMINATION_LINE,
)
from legalforecast.evals.corpus_manifest.beads_observation import (
    COORDINATION_BEAD_ID as _COORDINATION_BEAD_ID,
)
from legalforecast.evals.corpus_manifest.beads_observation import (
    SUCCESSOR_REGISTRY_PATH as _SUCCESSOR_REGISTRY_PATH,
)
from legalforecast.evals.corpus_manifest.beads_observation import (
    BeadsObservationError,
    parse_authentic_beads_comments,
)
from legalforecast.evals.corpus_manifest.records import registry_record
from legalforecast.evals.corpus_manifest.schema import load_signed_manifest_bytes
from legalforecast.evals.model_registry import (
    load_model_registry_bytes,
    require_official_registry_entries,
)
from legalforecast.immutable_io import (
    ImmutableIOError,
    publish_tree_create_only,
    read_single_link_file,
    write_file_create_only,
)
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.cohort_policy import (
    verify_cohort_policy,
    verify_observation_manifest,
)
from legalforecast.labeling.provider_journal import (
    ProviderJournalError,
    load_provider_cycle_caps_bytes,
    open_provider_journal_snapshot,
    provider_journal_durable_bytes,
    verify_provider_journal_identity,
)
from legalforecast.protocol.policy_artifacts import (
    OFFICIAL_SHARD_ABLATIONS,
    generate_execution_policy_v2,
    verify_execution_policy_v2,
    verify_labeling_policy,
)

_SHA256: Final = re.compile(r"[0-9a-f]{64}\Z")
_DECISIONS_NAME: Final = "execution-decisions-v2.json"
_POLICY_NAME: Final = "execution-policy-v2.json"
_BEADS_OBSERVATION_NAME: Final = "beads-observation-v2.json"
_RUN_CARD_NAME: Final = "run-cards/issue-manifest-execution-decisions-v2.json"
_NO_BASELINES_NAME: Final = "no-baselines.json"
_BEADS_SCHEMA: Final = str(MANIFEST_EXECUTION_DECISIONS_BEADS_OBSERVATION_V2)
_OFFICIAL_CASE_COUNT: Final = 100
_ABLATIONS: Final = tuple(OFFICIAL_SHARD_ABLATIONS)
_CURRENT_COHORT_OBSERVATION_SHA256: Final = (
    "033b1ed3a90be2f78ecb3387fc49df419c39868cf55d65eee5f262c1cc282721"
)
_CURRENT_COHORT_POLICY_SHA256: Final = (
    "d9bb6b40bf4914ed94e17b66b5ba2cfd2a0051dbb8dc1947269fe65886806216"
)
_CANONICAL_PROVIDER_JOURNAL_SUFFIX: Final = (
    "cycle-1/target-100-production-v4-ranked-reserve/paid-labeling/"
    "provider-attempts.sqlite3"
)
_POLICY_FIELDS: Final = frozenset(
    {
        "cycle_id",
        "cycle_series",
        "allow_no_baselines",
        "labeling_policy_sha256",
        "cohort_policy_sha256",
        "cohort_observation_manifest_sha256",
        "lifecycle",
        "shard_schedule",
        "concurrency_policy",
        "receipt_policy",
        "attempt_policy",
        "repeat_policy",
        "cadence_counts",
    }
)


class ExecutionDecisionsError(ValueError):
    """Raised when an authenticated execution-decision input is invalid."""


@dataclass(frozen=True, slots=True)
class ExecutionDecisionsBuild:
    """Canonical decisions, generated policy, and publication payloads."""

    decisions: Mapping[str, Any]
    execution_policy: Mapping[str, Any]
    run_card: Mapping[str, Any]
    payloads: Mapping[str, bytes]
    input_snapshots: Mapping[Path, bytes]


def issue_beads_observation(
    *,
    model_registry: Path,
    output: Path,
) -> Mapping[str, Any]:
    """Capture live ``bd comments --json`` bytes and issue their replay wrapper."""

    payload = _capture_beads_comments()
    registry_bytes = _read_regular(model_registry, "successor model registry")
    wrapper, encoded = _encode_beads_observation(
        payload,
        model_registry=model_registry,
        model_registry_bytes=registry_bytes,
    )
    _verify_beads_observation(
        encoded,
        manifest_digest=str(wrapper["evidence"]["manifest"]["manifest_sha256"]),
        model_registry=model_registry,
        model_registry_bytes=registry_bytes,
    )
    if _read_regular(model_registry, "successor model registry") != registry_bytes:
        raise ExecutionDecisionsError("model registry changed during issuance")
    try:
        write_file_create_only(output, encoded)
    except ImmutableIOError as exc:
        raise ExecutionDecisionsError(str(exc)) from exc
    if _read_regular(model_registry, "successor model registry") != registry_bytes:
        raise ExecutionDecisionsError("model registry changed during issuance")
    return wrapper


def issue_execution_decisions(
    *,
    owner_manifest: Path,
    forecast_output_dir: Path,
    model_registry: Path,
    provider_cycle_caps: Path,
    labeling_provider_cycle_caps: Path,
    provider_journal: Path,
    labeling_policy: Path,
    cohort_policy: Path,
    cohort_observation_manifest: Path,
    freeze_inputs_root: Path,
    output_root: Path,
    verify_freeze_inputs: Callable[[Path], Any],
) -> ExecutionDecisionsBuild:
    """Derive and create-only publish the official Cycle 1 decisions/policy."""

    build = _build(
        owner_manifest=owner_manifest,
        forecast_output_dir=forecast_output_dir,
        model_registry=model_registry,
        provider_cycle_caps=provider_cycle_caps,
        labeling_provider_cycle_caps=labeling_provider_cycle_caps,
        provider_journal=provider_journal,
        labeling_policy=labeling_policy,
        cohort_policy=cohort_policy,
        cohort_observation_manifest=cohort_observation_manifest,
        beads_observation_bytes=None,
        freeze_inputs_root=freeze_inputs_root,
        verify_freeze_inputs=verify_freeze_inputs,
    )
    _require_unchanged(build.input_snapshots)
    _publish_create_only(output_root, build.payloads)
    _require_unchanged(build.input_snapshots)
    return build


def verify_execution_decisions(
    output_root: Path, *, verify_freeze_inputs: Callable[[Path], Any]
) -> ExecutionDecisionsBuild:
    """Rebuild and verify a previously issued decisions/policy tree."""

    card_path = output_root / _RUN_CARD_NAME
    card_bytes = _read_regular(card_path, "execution-decision run card")
    card = _json_object(card_bytes, "execution-decision run card")
    if card_bytes != canonical_json_bytes(
        card,
        error_type=ExecutionDecisionsError,
        error_message="execution-decision run card is not canonical JSON",
    ):
        raise ExecutionDecisionsError("execution-decision run card is not canonical")
    if (
        card.get("schema_version") != str(MANIFEST_EXECUTION_DECISIONS_RUN_CARD_V2)
        or card.get("stage") != "issue-manifest-execution-decisions-v2"
        or card.get("status") != "completed"
        or card.get("provider_calls_made") != 0
        or card.get("paid_activity_executed") is not False
    ):
        raise ExecutionDecisionsError(
            "execution-decision run card is not provider-free"
        )
    inputs = _mapping(card.get("input_paths"), "run-card input_paths")
    beads_observation_bytes = _read_regular(
        output_root / _BEADS_OBSERVATION_NAME, "Beads observation"
    )
    build = _build(
        owner_manifest=Path(_required_text(inputs, "owner_manifest")),
        forecast_output_dir=Path(_required_text(inputs, "forecast_output_dir")),
        model_registry=Path(_required_text(inputs, "model_registry")),
        provider_cycle_caps=Path(_required_text(inputs, "provider_cycle_caps")),
        labeling_provider_cycle_caps=Path(
            _required_text(inputs, "labeling_provider_cycle_caps")
        ),
        provider_journal=Path(_required_text(inputs, "provider_journal")),
        labeling_policy=Path(_required_text(inputs, "labeling_policy")),
        cohort_policy=Path(_required_text(inputs, "cohort_policy")),
        cohort_observation_manifest=Path(
            _required_text(inputs, "cohort_observation_manifest")
        ),
        beads_observation_bytes=beads_observation_bytes,
        freeze_inputs_root=Path(_required_text(inputs, "freeze_inputs_root")),
        verify_freeze_inputs=verify_freeze_inputs,
    )
    if card_bytes != build.payloads[_RUN_CARD_NAME]:
        raise ExecutionDecisionsError("execution-decision run card does not reproduce")
    decisions_bytes = _read_regular(
        output_root / _DECISIONS_NAME, "execution decisions"
    )
    policy_bytes = _read_regular(output_root / _POLICY_NAME, "execution policy")
    expected_output_commitments = {
        name: _sha(payload)
        for name, payload in build.payloads.items()
        if name != _RUN_CARD_NAME
    }
    if card.get("output_commitments") != expected_output_commitments:
        raise ExecutionDecisionsError(
            "execution-decision output commitments do not reproduce"
        )
    if decisions_bytes != build.payloads[_DECISIONS_NAME]:
        raise ExecutionDecisionsError("execution decision bytes do not reproduce")
    if policy_bytes != build.payloads[_POLICY_NAME]:
        raise ExecutionDecisionsError("execution policy bytes do not reproduce")
    decisions = _json_object(decisions_bytes, "execution decisions")
    policy = _json_object(policy_bytes, "execution policy")
    verify_execution_policy_v2(policy, expected_cycle_id=decisions["cycle_id"])
    _require_unchanged(build.input_snapshots)
    return build


def _build(
    *,
    owner_manifest: Path,
    forecast_output_dir: Path,
    model_registry: Path,
    provider_cycle_caps: Path,
    labeling_provider_cycle_caps: Path,
    provider_journal: Path,
    labeling_policy: Path,
    cohort_policy: Path,
    cohort_observation_manifest: Path,
    beads_observation_bytes: bytes | None,
    freeze_inputs_root: Path,
    verify_freeze_inputs: Callable[[Path], Any],
) -> ExecutionDecisionsBuild:
    snapshots: dict[Path, bytes] = {}
    owner_bytes = _snapshot(owner_manifest, snapshots, "owner manifest")
    owner_record = _json_object(owner_bytes, "owner manifest")
    cycle_id = _required_sha(owner_record, "manifest_sha256")
    manifest = load_signed_manifest_bytes(owner_bytes, expected_digest=cycle_id)
    if len(manifest.cases) != _OFFICIAL_CASE_COUNT:
        raise ExecutionDecisionsError(
            "official execution requires exactly 100 manifest cases"
        )

    registry_bytes = _snapshot(model_registry, snapshots, "model registry")
    registry = load_model_registry_bytes(registry_bytes)
    entries = require_official_registry_entries(registry.entries)
    if len(entries) != 4:
        raise ExecutionDecisionsError(
            "official execution requires exactly four registry entries"
        )
    _require_successor_registry_safety(entries)
    registry_keys = tuple(sorted(entry.registry_key for entry in entries))

    forecast = _verify_forecast(
        forecast_output_dir,
        snapshots,
        cycle_id=manifest.cycle_id,
        manifest_digest=cycle_id,
        expected_case_ids=tuple(case.candidate_id for case in manifest.cases),
        registry_keys=registry_keys,
        registry_entries=entries,
        prediction_units_source=manifest.prediction_units_source.to_record(),
    )
    if manifest.cycle_id != _required_text(owner_record, "cycle_id"):
        raise ExecutionDecisionsError("owner manifest cycle_id is invalid")
    cycle_id_text = manifest.cycle_id

    caps_bytes = _snapshot(provider_cycle_caps, snapshots, "provider cycle caps")
    caps = load_provider_cycle_caps_bytes(caps_bytes, source=provider_cycle_caps)
    if caps.cycle_id != cycle_id_text:
        raise ExecutionDecisionsError("provider cycle caps cycle_id differs")
    caps_sha = _sha(caps_bytes)
    attempt_policy = dict(caps.execution_attempt_policy(caps_sha))

    labeling_caps_bytes = _snapshot(
        labeling_provider_cycle_caps,
        snapshots,
        "labeling provider cycle caps",
    )
    labeling_caps = load_provider_cycle_caps_bytes(
        labeling_caps_bytes, source=labeling_provider_cycle_caps
    )
    if labeling_caps.cycle_id != cycle_id_text:
        raise ExecutionDecisionsError("labeling provider cycle caps cycle_id differs")
    journal = _authenticate_provider_journal(
        provider_journal,
        cycle_id=labeling_caps.cycle_id,
        provider_cycle_caps_sha256=_sha(labeling_caps_bytes),
        snapshots=snapshots,
    )

    labeling_bytes = _snapshot(labeling_policy, snapshots, "labeling policy")
    labeling = _json_object(labeling_bytes, "labeling policy")
    verify_labeling_policy(labeling, expected_cycle_id=cycle_id_text)
    labeling_content = _mapping(labeling.get("policy"), "labeling policy")
    labeling_published = _required_text(labeling_content, "published_at")

    cohort_bytes = _snapshot(cohort_policy, snapshots, "cohort policy")
    cohort = _json_object(cohort_bytes, "cohort policy")
    cohort_policy_sha = verify_cohort_policy(cohort)
    if cohort_policy_sha != _CURRENT_COHORT_POLICY_SHA256:
        raise ExecutionDecisionsError(
            "cohort policy is not the verified current v3 policy"
        )
    cohort_content = _mapping(cohort.get("policy"), "cohort policy")
    if cohort_content.get("cycle_id") != cycle_id_text:
        raise ExecutionDecisionsError("cohort policy cycle_id differs")

    observation_bytes = _snapshot(
        cohort_observation_manifest, snapshots, "cohort observation manifest"
    )
    observation = _observation_records(observation_bytes)
    verify_observation_manifest(observation, policy_artifact=cohort)
    observation_sha = _sha(observation_bytes)
    if observation_sha != _CURRENT_COHORT_OBSERVATION_SHA256:
        raise ExecutionDecisionsError(
            "cohort observation manifest is not the verified current v3 bytes"
        )

    if beads_observation_bytes is None:
        _, beads_bytes = _encode_beads_observation(
            _capture_beads_comments(),
            model_registry=model_registry,
            model_registry_bytes=registry_bytes,
        )
    else:
        beads_bytes = beads_observation_bytes
    beads = _verify_beads_observation(
        beads_bytes,
        manifest_digest=cycle_id,
        model_registry=model_registry,
        model_registry_bytes=registry_bytes,
    )
    _require_provider_caps_and_owner_limit(
        entries=entries,
        attempt_policy=attempt_policy,
        beads=beads,
    )
    labeling_time = _parse_timestamp(labeling_published, "labeling policy published_at")
    labeling_started = _required_text(journal, "earliest_reserved_at")
    labeling_started_time = _parse_timestamp(
        labeling_started, "production_labeling_started_at"
    )
    if labeling_time > labeling_started_time:
        raise ExecutionDecisionsError(
            "labeling policy was not published before labeling started"
        )

    freeze_payloads = _verify_complete_freeze_inputs(
        freeze_inputs_root,
        snapshots,
        cycle_id=cycle_id_text,
        verifier=verify_freeze_inputs,
        owner_manifest=owner_manifest,
        model_registry=model_registry,
        forecast_output_dir=forecast_output_dir,
        owner_manifest_sha256=_sha(owner_bytes),
        model_registry_sha256=_sha(registry_bytes),
        forecast=forecast,
    )
    no_baselines_bytes = freeze_payloads[_NO_BASELINES_NAME]
    no_baselines = _json_object(no_baselines_bytes, "no-baselines sentinel")
    if (
        no_baselines.get("schema_version") != str(NO_BASELINES_V1)
        or no_baselines.get("cycle_id") != cycle_id_text
        or no_baselines.get("status") != "unavailable"
    ):
        raise ExecutionDecisionsError("no-baselines sentinel is not authenticated")

    decisions: dict[str, Any] = {
        "cycle_id": cycle_id_text,
        "cycle_series": "official",
        "allow_no_baselines": True,
        # Policy links are raw bytes, matching FrozenArtifact.sha256 and the
        # cross-artifact checks in protocol.freeze.
        "labeling_policy_sha256": _sha(labeling_bytes),
        "cohort_policy_sha256": _sha(cohort_bytes),
        "cohort_observation_manifest_sha256": observation_sha,
        "lifecycle": {
            "labeling_policy_published_at": labeling_published,
            "production_labeling_started_at": labeling_started,
        },
        "shard_schedule": {
            "shard_count": len(registry_keys) * len(_ABLATIONS),
            "dispatch_unit": "model_key_ablation",
            "shards": [
                {"model_key": key, "ablation": ablation}
                for key in registry_keys
                for ablation in _ABLATIONS
            ],
        },
        "concurrency_policy": {
            "mode": "shard_identity",
            "identity_fields": ["cycle_id", "model_key", "ablation"],
        },
        "receipt_policy": {
            "write_once_per_attempt": True,
            "identity_fields": ["workflow_run_id", "workflow_run_attempt"],
            "result_commitment_required": True,
        },
        "attempt_policy": attempt_policy,
        "repeat_policy": {"case_ids": [], "count": 1},
        "cadence_counts": {
            "clean_motion_count_source": "frozen_manifest",
            "prediction_unit_count_source": "frozen_units",
            "reject_operator_mismatch": True,
        },
        "authenticated_inputs": {
            "manifest_sha256": cycle_id,
            "run_inputs_sha256": forecast["run_inputs_sha256"],
            "model_registry_sha256": _sha(registry_bytes),
            "provider_cycle_caps_sha256": caps_sha,
            "labeling_provider_cycle_caps_sha256": _sha(labeling_caps_bytes),
            "provider_journal": journal,
            "labeling_policy_sha256": _sha(labeling_bytes),
            "cohort_policy_sha256": _sha(cohort_bytes),
            "cohort_observation_manifest_sha256": observation_sha,
            "beads_observation_sha256": _sha(beads_bytes),
            "beads_raw_observation_sha256": beads["raw_observation_sha256"],
            "beads_bead_id": beads["bead_id"],
            "beads_spend": {
                "ceiling_usd": beads["ceiling_usd"],
                "estimate_usd": beads["estimate_usd"],
            },
            "beads_line_sha256": beads["line_sha256"],
            "no_baselines_sha256": _sha(no_baselines_bytes),
            "request_count": len(manifest.cases) * len(registry_keys) * len(_ABLATIONS),
        },
    }
    policy_decisions = {
        key: value for key, value in decisions.items() if key in _POLICY_FIELDS
    }
    execution_policy = generate_execution_policy_v2(policy_decisions)
    payloads = {
        _DECISIONS_NAME: canonical_json_bytes(
            {"schema_version": str(MANIFEST_EXECUTION_DECISIONS_V2), **decisions},
            error_type=ExecutionDecisionsError,
            error_message="execution decisions are not canonical JSON",
        ),
        _POLICY_NAME: _policy_bytes(execution_policy),
        _BEADS_OBSERVATION_NAME: beads_bytes,
    }
    run_card = {
        "schema_version": str(MANIFEST_EXECUTION_DECISIONS_RUN_CARD_V2),
        "stage": "issue-manifest-execution-decisions-v2",
        "status": "completed",
        "cycle_id": cycle_id_text,
        "provider_calls_made": 0,
        "paid_activity_executed": False,
        "input_paths": {
            "owner_manifest": str(owner_manifest),
            "forecast_output_dir": str(forecast_output_dir),
            "model_registry": str(model_registry),
            "provider_cycle_caps": str(provider_cycle_caps),
            "labeling_provider_cycle_caps": str(labeling_provider_cycle_caps),
            "provider_journal": str(provider_journal),
            "labeling_policy": str(labeling_policy),
            "cohort_policy": str(cohort_policy),
            "cohort_observation_manifest": str(cohort_observation_manifest),
            "freeze_inputs_root": str(freeze_inputs_root),
        },
        "input_commitments": {
            str(path): _sha(payload)
            for path, payload in sorted(
                snapshots.items(), key=lambda item: str(item[0])
            )
        },
        "output_commitments": {
            name: _sha(payload) for name, payload in payloads.items()
        },
    }
    payloads[_RUN_CARD_NAME] = canonical_json_bytes(
        run_card,
        error_type=ExecutionDecisionsError,
        error_message="execution-decision run card is not canonical JSON",
    )
    return ExecutionDecisionsBuild(
        decisions={"schema_version": str(MANIFEST_EXECUTION_DECISIONS_V2), **decisions},
        execution_policy=execution_policy,
        run_card=run_card,
        payloads=payloads,
        input_snapshots=snapshots,
    )


def _capture_beads_comments() -> bytes:
    try:
        completed = subprocess.run(
            ["bd", "comments", _COORDINATION_BEAD_ID, "--json"],
            check=False,
            capture_output=True,
        )
    except OSError as exc:
        raise ExecutionDecisionsError(
            "cannot execute live bd comments capture"
        ) from exc
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ExecutionDecisionsError(
            f"live bd comments capture failed: {detail or completed.returncode}"
        )
    if not completed.stdout:
        raise ExecutionDecisionsError("live bd comments capture returned no bytes")
    return completed.stdout


def _encode_beads_observation(
    payload: bytes,
    *,
    model_registry: Path,
    model_registry_bytes: bytes,
) -> tuple[dict[str, Any], bytes]:
    evidence = _parse_authentic_beads_comments(
        payload,
        model_registry=model_registry,
        model_registry_bytes=model_registry_bytes,
    )
    wrapper = {
        "schema_version": _BEADS_SCHEMA,
        "issue_id": _COORDINATION_BEAD_ID,
        "model_registry_path": _SUCCESSOR_REGISTRY_PATH,
        "model_registry_sha256": _sha(model_registry_bytes),
        "raw_observation_sha256": _sha(payload),
        "raw_observation_base64": base64.b64encode(payload).decode("ascii"),
        "evidence": evidence,
    }
    encoded = canonical_json_bytes(
        wrapper,
        error_type=ExecutionDecisionsError,
        error_message="Beads observation is not canonical JSON",
    )
    return wrapper, encoded


def _authenticate_provider_journal(
    path: Path,
    *,
    cycle_id: str,
    provider_cycle_caps_sha256: str,
    snapshots: dict[Path, bytes],
) -> dict[str, Any]:
    if not path.resolve().as_posix().endswith(_CANONICAL_PROVIDER_JOURNAL_SUFFIX):
        raise ExecutionDecisionsError(
            "provider journal is not the canonical labeling journal"
        )
    try:
        durable_before = dict(provider_journal_durable_bytes(path))
        with closing(open_provider_journal_snapshot(path)) as snapshot:
            identity = verify_provider_journal_identity(
                path,
                cycle_id=cycle_id,
                provider_cycle_caps_sha256=provider_cycle_caps_sha256,
                snapshot=snapshot,
            )
            attempt_count = int(
                snapshot.execute("SELECT COUNT(*) FROM provider_attempts").fetchone()[0]
            )
            row = snapshot.execute(
                "SELECT logical_call_key, attempt_ordinal, stage, candidate_id, "
                "model_key, provider, account, prompt_sha256, "
                "model_registry_sha256, status, reserved_at, completed_at "
                "FROM provider_attempts ORDER BY reserved_at, logical_call_key, "
                "attempt_ordinal LIMIT 1"
            ).fetchone()
        durable_after = dict(provider_journal_durable_bytes(path))
    except (OSError, ProviderJournalError, sqlite3.Error) as exc:
        raise ExecutionDecisionsError(
            f"provider journal authentication failed: {exc}"
        ) from exc
    if durable_after != durable_before:
        raise ExecutionDecisionsError("provider journal changed during authentication")
    if attempt_count <= 0 or row is None:
        raise ExecutionDecisionsError(
            "provider journal contains no durable reservations"
        )
    earliest = {name: row[name] for name in row.keys()}
    reserved_at = earliest.get("reserved_at")
    if not isinstance(reserved_at, str):
        raise ExecutionDecisionsError(
            "provider journal earliest reservation lacks timestamp"
        )
    _parse_timestamp(reserved_at, "provider journal earliest reserved_at")
    for name, payload in durable_before.items():
        snapshots[path.parent / name] = payload
    return {
        "schema_version": identity.schema_version,
        "cycle_id": identity.cycle_id,
        "provider_cycle_caps_sha256": provider_cycle_caps_sha256,
        "canonical_path": identity.canonical_path,
        "durable_files": {
            name: {"sha256": _sha(payload), "size_bytes": len(payload)}
            for name, payload in sorted(durable_before.items())
        },
        "attempt_count": attempt_count,
        "earliest_reserved_at": reserved_at,
        "earliest_reservation": earliest,
    }


def _require_successor_registry_safety(entries: tuple[Any, ...]) -> None:
    from legalforecast.evals.corpus_manifest.beads_observation import (
        SUCCESSOR_REGISTRY_KEYS,
    )

    if frozenset(entry.registry_key for entry in entries) != SUCCESSOR_REGISTRY_KEYS:
        raise ExecutionDecisionsError(
            "model registry does not contain the successor set"
        )
    unsafe = sorted(
        entry.registry_key
        for entry in entries
        if entry.network_disabled is not True
        or entry.search_disabled is not True
        or entry.temperature != 0.0
        or entry.top_p != 1.0
        or entry.tool_policy.value != "controlled_docket_tool_only"
    )
    if unsafe:
        raise ExecutionDecisionsError(
            f"successor model registry has unsafe execution settings: {unsafe}"
        )


def _require_provider_caps_and_owner_limit(
    *,
    entries: tuple[Any, ...],
    attempt_policy: Mapping[str, Any],
    beads: Mapping[str, Any],
) -> None:
    raw_caps = attempt_policy.get("provider_account_caps")
    if not isinstance(raw_caps, list):
        raise ExecutionDecisionsError("provider attempt caps are not an array")
    caps = [
        _mapping(value, "provider account cap")
        for value in cast(list[object], raw_caps)
    ]
    registry_providers = {entry.provider.lower() for entry in entries}
    cap_providers = {_required_text(cap, "provider").lower() for cap in caps}
    if cap_providers != registry_providers or len(caps) != len(cap_providers):
        raise ExecutionDecisionsError(
            "provider attempt caps do not exactly cover registry providers"
        )
    total_microusd = 0
    for cap in caps:
        amount = cap.get("cap_microusd")
        if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
            raise ExecutionDecisionsError("provider cap_microusd must be positive")
        total_microusd += amount
    ceiling = _money(_required_text(beads, "ceiling_usd"), "ceiling_usd")
    estimate = _money(_required_text(beads, "estimate_usd"), "estimate_usd")
    if estimate > ceiling:
        raise ExecutionDecisionsError("provider estimate exceeds owner ceiling")
    if Decimal(total_microusd) / Decimal(1_000_000) > ceiling:
        raise ExecutionDecisionsError("provider caps exceed owner-approved ceiling")


def _money(value: str, name: str) -> Decimal:
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise ExecutionDecisionsError(f"{name} must be decimal USD") from exc
    exponent = amount.as_tuple().exponent
    if (
        not amount.is_finite()
        or amount < 0
        or not isinstance(exponent, int)
        or exponent < -2
    ):
        raise ExecutionDecisionsError(f"{name} must be non-negative cents")
    return amount


def _verify_complete_freeze_inputs(
    root: Path,
    snapshots: dict[Path, bytes],
    *,
    cycle_id: str,
    verifier: Callable[[Path], Any],
    owner_manifest: Path,
    model_registry: Path,
    forecast_output_dir: Path,
    owner_manifest_sha256: str,
    model_registry_sha256: str,
    forecast: Mapping[str, Any],
) -> dict[str, bytes]:
    """Replay the complete generic issuer and bind every published byte."""

    try:
        build = verifier(root)
    except Exception as exc:
        raise ExecutionDecisionsError(
            "generic freeze inputs fail complete replay verification"
        ) from exc
    payloads = getattr(build, "payloads", None)
    run_card = getattr(build, "run_card", None)
    expected_names = {
        "prompt-contract.json",
        "scorer-contract.json",
        "harness-contract.json",
        _NO_BASELINES_NAME,
        "complete-exclusion-ledger.jsonl",
        "run-cards/issue-manifest-freeze-inputs.json",
    }
    if not isinstance(payloads, Mapping) or not isinstance(run_card, Mapping):
        raise ExecutionDecisionsError(
            "generic freeze verifier returned an incomplete result"
        )
    payload_map = cast(Mapping[str, object], payloads)
    run_card_map = cast(Mapping[str, Any], run_card)
    if set(payload_map) != expected_names or run_card_map.get("cycle_id") != cycle_id:
        raise ExecutionDecisionsError(
            "generic freeze verifier returned an incomplete result"
        )
    input_paths = _mapping(run_card_map.get("input_paths"), "freeze input_paths")
    for name, expected in (
        ("owner_manifest", owner_manifest),
        ("model_registry", model_registry),
        ("forecast_output_dir", forecast_output_dir),
    ):
        actual = Path(_required_text(input_paths, name))
        if actual.resolve() != expected.resolve():
            raise ExecutionDecisionsError(
                f"generic freeze run card {name} is not cross-bound"
            )
    verified: dict[str, bytes] = {}
    resolved_root = root.resolve()
    for name in sorted(expected_names):
        path = (root / name).resolve()
        try:
            path.relative_to(resolved_root)
        except ValueError as exc:
            raise ExecutionDecisionsError(
                "generic freeze input escapes its output root"
            ) from exc
        payload = _snapshot(path, snapshots, f"generic freeze input {name}")
        expected = payload_map[name]
        if not isinstance(expected, bytes) or payload != expected:
            raise ExecutionDecisionsError(
                f"generic freeze verifier bytes differ: {name}"
            )
        verified[name] = payload
    prompt = _json_object(verified["prompt-contract.json"], "prompt contract")
    replay = _mapping(prompt.get("prompt_replay"), "prompt replay")
    expected_replay = {
        "owner_manifest_bytes_sha256": owner_manifest_sha256,
        "model_registry_sha256": model_registry_sha256,
        "run_inputs_sha256": forecast["run_inputs_sha256"],
        "run_record_sha256": forecast["run_record_sha256"],
        "packet_count": _OFFICIAL_CASE_COUNT * len(_ABLATIONS),
        "candidate_count": _OFFICIAL_CASE_COUNT,
        "prompt_commitments": forecast["prompt_commitments"],
    }
    for name, expected in expected_replay.items():
        if replay.get(name) != expected:
            raise ExecutionDecisionsError(
                f"generic freeze prompt replay {name} is not cross-bound"
            )
    return verified


def _verify_forecast(
    root: Path,
    snapshots: dict[Path, bytes],
    *,
    cycle_id: str,
    manifest_digest: str,
    expected_case_ids: tuple[str, ...],
    registry_keys: tuple[str, ...],
    registry_entries: tuple[Any, ...],
    prediction_units_source: Mapping[str, Any],
) -> dict[str, Any]:
    record_path = root / "manifest-mode-run-record.json"
    inputs_path = root / "run-inputs.json"
    record_bytes = _snapshot(record_path, snapshots, "manifest forecast run record")
    inputs_bytes = _snapshot(inputs_path, snapshots, "manifest forecast run inputs")
    record = _json_object(record_bytes, "manifest forecast run record")
    inputs = _json_object(inputs_bytes, "manifest forecast run inputs")
    generated_at = _required_text(record, "generated_at")
    _parse_timestamp(generated_at, "manifest forecast generated_at")
    if (
        record.get("schema_version") != str(MANIFEST_MODE_FORECAST_RUN_RECORD_V1)
        or record.get("manifest_sha256") != manifest_digest
        or record.get("cycle_id") != cycle_id
        or inputs.get("cycle_id") != cycle_id
        or inputs.get("generated_at") != generated_at
        or record.get("entry_mode") != "owner_signed_manifest"
        or record.get("case_count") != len(expected_case_ids)
        or record.get("packet_count") != len(expected_case_ids) * len(_ABLATIONS)
        or record.get("packet_ablations") != list(_ABLATIONS)
        or record.get("provider_calls_made") != 0
        or record.get("docket_tool_enabled") is not False
        or record.get("required_eval_run_case_flags") != ["--no-docket-tool"]
    ):
        raise ExecutionDecisionsError(
            "manifest forecast is not authenticated no-docket input"
        )
    models = _mapping_list(record.get("evaluation_models"), "evaluation_models")
    if models != registry_record(registry_entries):
        raise ExecutionDecisionsError("forecast run record registry differs")
    actual_keys = tuple(
        sorted(
            f"{_required_text(row, 'provider')}:{_required_text(row, 'model_id')}"
            for row in models
        )
    )
    if actual_keys != registry_keys:
        raise ExecutionDecisionsError("forecast run record registry differs")
    signature = _mapping(
        record.get("owner_signature_reference"), "owner_signature_reference"
    )
    _required_text(signature, "bead_id")
    expected_approval = (
        f"I approve corpus manifest {manifest_digest} as the frozen Cycle 1 "
        "forecast corpus."
    )
    if _required_text(signature, "approval_line") != expected_approval:
        raise ExecutionDecisionsError("owner manifest approval line is not verbatim")
    if record.get("prediction_units_source") != dict(prediction_units_source):
        raise ExecutionDecisionsError(
            "forecast prediction-unit source is not manifest-bound"
        )
    packets = _mapping_list(inputs.get("model_packets"), "model_packets")
    if len(packets) != len(expected_case_ids) * len(_ABLATIONS):
        raise ExecutionDecisionsError("forecast packet count differs from manifest")
    expected_candidates = set(expected_case_ids)
    if len(expected_candidates) != len(expected_case_ids):
        raise ExecutionDecisionsError("manifest case IDs are not unique")
    prompt_commitments = _mapping(
        record.get("prompt_commitments"), "forecast prompt_commitments"
    )
    seen: set[tuple[str, str]] = set()
    for packet in packets:
        candidate = _required_text(packet, "candidate_id")
        if candidate not in expected_candidates:
            raise ExecutionDecisionsError(
                "forecast packet candidate is absent from signed manifest"
            )
        ablation = _required_text(packet, "ablation")
        pair = (candidate, ablation)
        if ablation not in _ABLATIONS or pair in seen:
            raise ExecutionDecisionsError(
                "forecast packet ablation coverage is invalid"
            )
        seen.add(pair)
        key = _required_text(packet, "packet_object_key")
        if not key.startswith("model-packets/"):
            raise ExecutionDecisionsError("forecast packet path is unsafe")
        packet_path = root / key
        resolved_packet_path = packet_path.resolve()
        try:
            resolved_packet_path.relative_to(root.resolve())
        except ValueError as exc:
            raise ExecutionDecisionsError(
                "forecast packet escapes output root"
            ) from exc
        packet_bytes = _snapshot(packet_path, snapshots, f"forecast packet {key}")
        if _sha(packet_bytes) != _required_sha(packet, "packet_sha256"):
            raise ExecutionDecisionsError(f"forecast packet changed: {key}")
        prompt_sha = _required_sha(packet, "prompt_sha256")
        prompt_key = f"{candidate}:{ablation}"
        if prompt_commitments.get(prompt_key) != prompt_sha:
            raise ExecutionDecisionsError("forecast prompt commitment differs")
    expected = {
        (candidate, ablation)
        for candidate in expected_candidates
        for ablation in _ABLATIONS
    }
    if seen != expected:
        raise ExecutionDecisionsError("forecast packet ablations are incomplete")
    return {
        "run_inputs_sha256": _sha(inputs_bytes),
        "run_record_sha256": _sha(record_bytes),
        "prompt_commitments": dict(sorted(prompt_commitments.items())),
        "generated_at": generated_at,
    }


def _observation_records(payload: bytes) -> tuple[dict[str, Any], ...]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(payload.splitlines(), start=1):
        if not line.strip():
            raise ExecutionDecisionsError(
                f"cohort observation manifest has a blank line at {line_number}"
            )
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ExecutionDecisionsError(
                f"cohort observation manifest line {line_number} is not JSON"
            ) from exc
        if not isinstance(value, dict):
            raise ExecutionDecisionsError(
                f"cohort observation manifest line {line_number} is not an object"
            )
        records.append(cast(dict[str, Any], value))
    return tuple(records)


def _verify_beads_observation(
    payload: bytes,
    *,
    manifest_digest: str,
    model_registry: Path,
    model_registry_bytes: bytes | None = None,
) -> dict[str, Any]:
    record = _json_object(payload, "Beads observation")
    if set(record) != {
        "schema_version",
        "issue_id",
        "model_registry_path",
        "model_registry_sha256",
        "raw_observation_sha256",
        "raw_observation_base64",
        "evidence",
    }:
        raise ExecutionDecisionsError("Beads observation fields are not exact")
    if (
        record.get("schema_version") != _BEADS_SCHEMA
        or record.get("issue_id") != _COORDINATION_BEAD_ID
        or record.get("model_registry_path") != _SUCCESSOR_REGISTRY_PATH
    ):
        raise ExecutionDecisionsError("Beads observation schema or issue differs")
    registry_payload = model_registry_bytes or _read_regular(
        model_registry, "successor model registry"
    )
    if _sha(registry_payload) != _required_sha(record, "model_registry_sha256"):
        raise ExecutionDecisionsError("Beads model registry digest differs")
    raw_b64 = _required_text(record, "raw_observation_base64")
    try:
        raw = base64.b64decode(raw_b64, validate=True)
    except (ValueError, TypeError) as exc:
        raise ExecutionDecisionsError(
            "Beads raw observation is not canonical base64"
        ) from exc
    if _sha(raw) != _required_sha(record, "raw_observation_sha256"):
        raise ExecutionDecisionsError("Beads raw observation digest differs")
    replayed = _parse_authentic_beads_comments(
        raw,
        model_registry=model_registry,
        model_registry_bytes=registry_payload,
    )
    evidence = _mapping(record.get("evidence"), "Beads evidence")
    if dict(evidence) != replayed:
        raise ExecutionDecisionsError("Beads evidence does not replay from raw bytes")
    manifest = _mapping(evidence.get("manifest"), "manifest evidence")
    if manifest.get("manifest_sha256") != manifest_digest:
        raise ExecutionDecisionsError("Beads manifest approval digest differs")
    contamination = _mapping(evidence.get("contamination"), "contamination evidence")
    if contamination.get("text") != _CONTAMINATION_LINE:
        raise ExecutionDecisionsError("Beads contamination ruling differs")
    spend = _mapping(evidence.get("final_provider_spend"), "spend evidence")
    return {
        "line_sha256": {
            name: _required_sha(_mapping(evidence[name], name), "text_sha256")
            for name in (
                "manifest",
                "contamination",
                "final_provider_spend",
            )
        },
        "bead_id": _COORDINATION_BEAD_ID,
        "raw_observation_sha256": _required_sha(record, "raw_observation_sha256"),
        "ceiling_usd": _required_text(spend, "ceiling_usd"),
        "estimate_usd": _required_text(spend, "estimate_usd"),
    }


def _parse_authentic_beads_comments(
    payload: bytes,
    *,
    model_registry: Path,
    model_registry_bytes: bytes | None = None,
) -> dict[str, Any]:
    """Translate the focused Beads parser's error into this issuer's domain."""

    try:
        return parse_authentic_beads_comments(
            payload,
            model_registry=model_registry,
            model_registry_bytes=model_registry_bytes,
        )
    except BeadsObservationError as exc:
        raise ExecutionDecisionsError(str(exc)) from exc


def _policy_bytes(policy: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(policy, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()


def _publish_create_only(root: Path, payloads: Mapping[str, bytes]) -> None:
    try:
        publish_tree_create_only(root, payloads)
    except ImmutableIOError as exc:
        raise ExecutionDecisionsError(str(exc)) from exc


def _snapshot(path: Path, snapshots: dict[Path, bytes], label: str) -> bytes:
    payload = _read_regular(path, label)
    snapshots[path] = payload
    return payload


def _require_unchanged(snapshots: Mapping[Path, bytes]) -> None:
    for path, expected in snapshots.items():
        if _read_regular(path, path.name) != expected:
            raise ExecutionDecisionsError(f"input changed during issuance: {path}")


def _read_regular(path: Path, label: str) -> bytes:
    try:
        return read_single_link_file(path, label=label)
    except ImmutableIOError as exc:
        raise ExecutionDecisionsError(str(exc)) from exc


def _json_object(payload: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ExecutionDecisionsError(f"{label} is not JSON") from exc
    if not isinstance(value, dict):
        raise ExecutionDecisionsError(f"{label} must be an object")
    return cast(dict[str, Any], value)


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ExecutionDecisionsError(f"{label} must be an object")
    return cast(Mapping[str, Any], value)


def _mapping_list(value: object, label: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        raise ExecutionDecisionsError(f"{label} must be an array")
    return [_mapping(item, label) for item in cast(list[object], value)]


def _required_text(record: Mapping[str, Any], name: str) -> str:
    value = record.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ExecutionDecisionsError(f"{name} must be a non-empty string")
    return value


def _required_sha(record: Mapping[str, Any], name: str) -> str:
    value = _required_text(record, name)
    if _SHA256.fullmatch(value) is None:
        raise ExecutionDecisionsError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _parse_timestamp(value: str, name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExecutionDecisionsError(f"{name} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ExecutionDecisionsError(f"{name} must be timezone-aware")
    return parsed
