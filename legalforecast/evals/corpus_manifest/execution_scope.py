"""Provider-neutral execution plans and per-model official scopes.

The deferred v2 execution policy is deliberately an all-model authority.  This
module is the additive successor for official sharding: the v3 plan is a
complete, provider-free description of the frozen run and has no execution
authority; a v1 scope is the separately authenticated owner decision for one
registry model.  A provider cell must present both artifacts before it can
open credentials.
"""

from __future__ import annotations

import base64
import json
import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Final, cast

from legalforecast.contracts import RAW_BYTES_RAW_SHA256_V1
from legalforecast.contracts.schemas import (
    EXECUTION_POLICY_V3,
    EXECUTION_SCOPE_V1,
    RAW_BYTES_RAW_SHA256_COMMITMENT_V1,
)
from legalforecast.evals.model_registry import (
    ModelRegistry,
    ModelRegistryEntry,
    model_registry_entry_sha256,
    require_official_registry_entries,
)
from legalforecast.immutable_io import ImmutableIOError, write_file_create_only
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.protocol.manifest import hash_payload

EXECUTION_POLICY_V3_SCHEMA_VERSION: Final = str(EXECUTION_POLICY_V3)
EXECUTION_SCOPE_SCHEMA_VERSION: Final = str(EXECUTION_SCOPE_V1)
OFFICIAL_SCOPE_ABLATIONS: Final = ("full_packet", "metadata_only")
OFFICIAL_CASE_COUNT: Final = 100
OFFICIAL_CALL_COUNT: Final = 200
_SHA256: Final = re.compile(r"[0-9a-f]{64}\Z")
_USD: Final = re.compile(r"[0-9]+(?:\.[0-9]+)?\Z")
_OWNER_USD: Final = re.compile(r"[0-9]+(?:\.[0-9]{1,2})?\Z")
_OWNER_COMMENT_FIELDS: Final = frozenset(
    {"id", "issue_id", "author", "text", "created_at"}
)
_OWNER_APPROVAL: Final = re.compile(
    r"I approve up to USD (?P<ceiling>[0-9]+(?:\.[0-9]{1,2})?) "
    r"of provider spend for model `?(?P<model>[^` ]+)`? in the Cycle 1 "
    r"forecast run, estimated USD (?P<estimate>[0-9]+(?:\.[0-9]{1,2})?)\.\Z"
)
_PLAN_FIELDS: Final = frozenset(
    {
        "cycle_id",
        "cycle_series",
        "authorization_mode",
        "provider_execution_authorized",
        "model_scope_required",
        "common_frozen_inputs",
        "model_registry_entries",
        "shard_schedule",
        "concurrency_policy",
        "attempt_policy",
        "repeat_policy",
        "receipt_policy",
    }
)
_COMMON_INPUT_FIELDS: Final = frozenset(
    {
        "freeze_bundle_sha256",
        "manifest_sha256",
        "run_input_manifest_sha256",
        "model_registry_sha256",
        "run_card_sha256",
    }
)
_SCOPE_FIELDS: Final = frozenset(
    {
        "cycle_id",
        "common_plan_sha256",
        "common_plan_artifact_sha256",
        "common_frozen_inputs",
        "model_key",
        "registry_entry_sha256",
        "registry_entry",
        "selected_ablations",
        "case_count",
        "call_count",
        "cost_projection_receipt_sha256",
        "projected_cost_usd",
        "owner_ceiling_usd",
        "owner_evidence",
        "provider_authority",
    }
)


class ExecutionScopeError(ValueError):
    """Raised when a plan or model scope is incomplete or has drifted."""


def generate_execution_policy_v3(
    plan: Mapping[str, Any],
) -> dict[str, Any]:
    """Create the non-authorizing complete official execution plan artifact."""

    normalized = _validate_plan(plan)
    return {
        "schema_version": EXECUTION_POLICY_V3_SCHEMA_VERSION,
        "policy": normalized,
        "policy_sha256": _content_hash(normalized),
    }


def verify_execution_policy_v3(
    artifact: Mapping[str, Any],
    *,
    expected_cycle_id: str | None = None,
    expected_sha256: str | None = None,
) -> str:
    """Verify a v3 plan and return its policy-content digest."""

    _exact_keys(artifact, {"schema_version", "policy", "policy_sha256"}, "plan")
    if artifact.get("schema_version") != EXECUTION_POLICY_V3_SCHEMA_VERSION:
        raise ExecutionScopeError("unsupported execution policy v3 schema")
    policy = _mapping(artifact.get("policy"), "plan policy")
    actual = _content_hash(policy)
    if _sha(artifact.get("policy_sha256"), "policy_sha256") != actual:
        raise ExecutionScopeError("plan policy_sha256 does not match policy content")
    normalized = _validate_plan(policy)
    if expected_cycle_id is not None and normalized["cycle_id"] != expected_cycle_id:
        raise ExecutionScopeError("plan cycle_id does not match expected cycle")
    if expected_sha256 is not None and actual != _sha(
        expected_sha256, "expected_sha256"
    ):
        raise ExecutionScopeError("plan digest does not match expected digest")
    return actual


def issue_execution_plan(
    *,
    cycle_id: str,
    model_registry: Path,
    common_frozen_inputs: Mapping[str, str],
    run_card_sha256: str | None = None,
    output: Path | None = None,
) -> dict[str, Any]:
    """Issue a provider-free complete plan without granting provider authority.

    ``common_frozen_inputs`` contains exact byte commitments.  The model
    registry is read once, checked for official eligibility, and re-read before
    optional create-only publication so a registry replacement cannot be
    smuggled into the plan.
    """

    registry_path = Path(model_registry)
    registry_bytes = _read_bytes(registry_path, "model registry")
    registry = _official_registry(registry_bytes)
    inputs = dict(common_frozen_inputs)
    if run_card_sha256 is not None:
        inputs["run_card_sha256"] = run_card_sha256
    _validate_common_inputs(inputs)
    registry_sha256 = _sha256_bytes(registry_bytes)
    if inputs["model_registry_sha256"] != registry_sha256:
        raise ExecutionScopeError("model registry hash does not match supplied inputs")
    entries = {
        entry.registry_key: {
            "registry_entry_sha256": model_registry_entry_sha256(entry),
            "registry_entry": entry.to_record(),
        }
        for entry in registry.entries
    }
    plan: dict[str, Any] = {
        "cycle_id": _text(cycle_id, "cycle_id"),
        "cycle_series": "official",
        "authorization_mode": "model_scope_required",
        "provider_execution_authorized": False,
        "model_scope_required": True,
        "common_frozen_inputs": inputs,
        "model_registry_entries": entries,
        "shard_schedule": {
            "shard_count": len(entries) * len(OFFICIAL_SCOPE_ABLATIONS),
            "dispatch_unit": "model_key_ablation",
            "shards": [
                {"model_key": key, "ablation": ablation}
                for key in sorted(entries)
                for ablation in OFFICIAL_SCOPE_ABLATIONS
            ],
        },
        "concurrency_policy": {
            "mode": "shard_identity",
            "identity_fields": ["cycle_id", "model_key", "ablation"],
        },
        "attempt_policy": {"scope_required": True},
        "repeat_policy": {"case_ids": [], "count": 1},
        "receipt_policy": {
            "write_once_per_attempt": True,
            "scope_required": True,
            "result_commitment_required": True,
        },
    }
    artifact = generate_execution_policy_v3(plan)
    if _read_bytes(registry_path, "model registry") != registry_bytes:
        raise ExecutionScopeError("model registry changed during plan issuance")
    if output is not None:
        _write_json_create_only(Path(output), artifact)
    return artifact


def issue_model_execution_scope(
    *,
    common_plan: Path | Mapping[str, Any],
    model_registry: Path,
    model_key: str,
    cost_projection: Path | Mapping[str, Any],
    owner_ceiling_usd: str,
    owner_evidence: Path | Mapping[str, Any] | bytes | None = None,
    owner_bead_id: str | None = None,
    provider_authority: Mapping[str, Any],
    output: Path | None = None,
) -> dict[str, Any]:
    """Issue one exact-model scope against a complete v3 plan.

    The cost receipt must be the exact one-model/two-ablation 100x2 matrix.
    The scope is therefore reusable by both paid ablation shards, while no
    second model can consume it.
    """

    plan_artifact = _load_json_source(common_plan, "common plan")
    plan_digest = verify_execution_policy_v3(plan_artifact)
    plan = _mapping(plan_artifact["policy"], "common plan policy")
    registry_path = Path(model_registry)
    registry_bytes = _read_bytes(registry_path, "model registry")
    registry = _official_registry(registry_bytes)
    key = _text(model_key, "model_key")
    try:
        entry = _registry_entry(registry, key)
    except (KeyError, ValueError) as exc:
        raise ExecutionScopeError(
            f"model_key is not in the frozen registry: {key}"
        ) from exc
    plan_entries = _mapping(plan.get("model_registry_entries"), "plan registry entries")
    plan_entry = _mapping(plan_entries.get(key), f"plan registry entry {key}")
    entry_digest = model_registry_entry_sha256(entry)
    if (
        plan_entry.get("registry_entry_sha256") != entry_digest
        or plan_entry.get("registry_entry") != entry.to_record()
    ):
        raise ExecutionScopeError("registry entry does not match common plan")
    if plan.get("common_frozen_inputs", {}).get(
        "model_registry_sha256"
    ) != _sha256_bytes(registry_bytes):
        raise ExecutionScopeError("model registry does not match common plan")
    cost_artifact = _load_json_source(cost_projection, "cost projection receipt")
    cost_digest = _verify_cost_receipt(
        cost_artifact,
        cycle_id=_text(plan.get("cycle_id"), "cycle_id"),
        model_key=key,
    )
    ceiling = _money(owner_ceiling_usd, "owner_ceiling_usd")
    projected = _money(
        _text(
            cost_artifact.get("projected_model_cost_usd"), "projected_model_cost_usd"
        ),
        "projected_model_cost_usd",
    )
    if projected > ceiling:
        raise ExecutionScopeError("projected cost exceeds owner ceiling")
    if owner_evidence is None:
        if owner_bead_id is None:
            raise ExecutionScopeError(
                "live model-scope issuance requires an owner Beads issue id"
            )
        from legalforecast.evals.corpus_manifest.execution_decisions import (
            capture_beads_comments,
        )

        owner_evidence = capture_beads_comments(owner_bead_id)
    elif isinstance(owner_evidence, Mapping):
        raise ExecutionScopeError(
            "model-scope issuance cannot accept a caller-authored owner wrapper"
        )
    evidence = _owner_evidence(
        owner_evidence,
        model_key=key,
        projected_cost=projected,
        owner_ceiling=ceiling,
        expected_bead_id=owner_bead_id,
    )
    authority = _validate_provider_authority(
        provider_authority,
        provider=entry.provider,
        projected_cost=projected,
        owner_ceiling=ceiling,
        cycle_id=cast(str, plan["cycle_id"]),
        model_key=key,
    )
    common_inputs = dict(
        _mapping(plan.get("common_frozen_inputs"), "common_frozen_inputs")
    )
    scope: dict[str, Any] = {
        "cycle_id": plan["cycle_id"],
        "common_plan_sha256": plan_digest,
        "common_plan_artifact_sha256": hash_payload(plan_artifact),
        "common_frozen_inputs": common_inputs,
        "model_key": key,
        "registry_entry_sha256": entry_digest,
        "registry_entry": entry.to_record(),
        "selected_ablations": list(OFFICIAL_SCOPE_ABLATIONS),
        "case_count": OFFICIAL_CASE_COUNT,
        "call_count": OFFICIAL_CALL_COUNT,
        "cost_projection_receipt_sha256": cost_digest,
        "projected_cost_usd": _format_money(projected),
        "owner_ceiling_usd": _format_money(ceiling),
        "owner_evidence": evidence,
        "provider_authority": authority,
    }
    artifact = {
        "schema_version": EXECUTION_SCOPE_SCHEMA_VERSION,
        "scope": scope,
        "scope_sha256": hash_payload(scope),
    }
    verify_execution_scope(
        artifact,
        common_plan=plan_artifact,
        model_registry=registry_path,
        cost_projection=cost_artifact,
        owner_evidence=evidence,
        provider_authority=authority,
        expected_model_key=key,
    )
    if _read_bytes(registry_path, "model registry") != registry_bytes:
        raise ExecutionScopeError("model registry changed during scope issuance")
    if output is not None:
        _write_json_create_only(Path(output), artifact)
    return artifact


def verify_execution_scope(
    artifact: Mapping[str, Any],
    *,
    common_plan: Path | Mapping[str, Any],
    model_registry: Path,
    cost_projection: Path | Mapping[str, Any],
    owner_evidence: Path | Mapping[str, Any] | bytes | None = None,
    provider_authority: Mapping[str, Any],
    expected_model_key: str | None = None,
    expected_ablation: str | None = None,
) -> str:
    """Verify a scope and all source bytes it authenticates."""

    _exact_keys(artifact, {"schema_version", "scope", "scope_sha256"}, "scope artifact")
    if artifact.get("schema_version") != EXECUTION_SCOPE_SCHEMA_VERSION:
        raise ExecutionScopeError("unsupported execution scope schema")
    scope = _mapping(artifact.get("scope"), "scope")
    _exact_keys(scope, set(_SCOPE_FIELDS), "scope")
    actual = hash_payload(scope)
    if _sha(artifact.get("scope_sha256"), "scope_sha256") != actual:
        raise ExecutionScopeError("scope_sha256 does not match scope content")
    plan_artifact = _load_json_source(common_plan, "common plan")
    plan_digest = verify_execution_policy_v3(plan_artifact)
    if scope.get("common_plan_sha256") != plan_digest:
        raise ExecutionScopeError("scope common plan digest drift")
    if scope.get("common_plan_artifact_sha256") != hash_payload(plan_artifact):
        raise ExecutionScopeError("scope common plan artifact drift")
    plan = _mapping(plan_artifact["policy"], "common plan policy")
    if scope.get("cycle_id") != plan.get("cycle_id"):
        raise ExecutionScopeError("scope cycle_id does not match common plan")
    key = _text(scope.get("model_key"), "model_key")
    if expected_model_key is not None and key != _text(
        expected_model_key, "expected_model_key"
    ):
        raise ExecutionScopeError("scope model_key is not the selected model")
    if expected_ablation is not None and expected_ablation not in scope.get(
        "selected_ablations", ()
    ):
        raise ExecutionScopeError("scope does not authorize selected ablation")
    registry_path = Path(model_registry)
    registry_bytes = _read_bytes(registry_path, "model registry")
    registry = _official_registry(registry_bytes)
    try:
        entry = _registry_entry(registry, key)
    except (KeyError, ValueError) as exc:
        raise ExecutionScopeError(
            "scope model_key is not authorized by registry"
        ) from exc
    if scope.get("common_frozen_inputs") != plan.get("common_frozen_inputs"):
        raise ExecutionScopeError("scope common frozen inputs drift")
    if scope["common_frozen_inputs"].get("model_registry_sha256") != _sha256_bytes(
        registry_bytes
    ):
        raise ExecutionScopeError("scope model registry hash drift")
    entry_digest = model_registry_entry_sha256(entry)
    if (
        scope.get("registry_entry_sha256") != entry_digest
        or scope.get("registry_entry") != entry.to_record()
    ):
        raise ExecutionScopeError("scope registry entry drift")
    _require_plan_registry_entry(plan, key, entry)
    cost_artifact = _load_json_source(cost_projection, "cost projection receipt")
    cost_digest = _verify_cost_receipt(
        cost_artifact, cycle_id=cast(str, plan["cycle_id"]), model_key=key
    )
    if scope.get("cost_projection_receipt_sha256") != cost_digest:
        raise ExecutionScopeError("scope cost projection drift")
    projected = _money(
        _text(scope.get("projected_cost_usd"), "projected_cost_usd"),
        "projected_cost_usd",
    )
    ceiling = _money(
        _text(scope.get("owner_ceiling_usd"), "owner_ceiling_usd"), "owner_ceiling_usd"
    )
    embedded_evidence = _mapping(scope.get("owner_evidence"), "scope.owner_evidence")
    embedded_bead_id = _text(embedded_evidence.get("bead_id"), "owner_evidence.bead_id")
    evidence = _owner_evidence(
        embedded_evidence if owner_evidence is None else owner_evidence,
        model_key=key,
        projected_cost=projected,
        owner_ceiling=ceiling,
        expected_bead_id=embedded_bead_id,
    )
    if scope.get("owner_evidence") != evidence:
        raise ExecutionScopeError("scope owner evidence drift")
    if (
        _money(
            _text(
                cost_artifact.get("projected_model_cost_usd"),
                "projected_model_cost_usd",
            ),
            "projected_model_cost_usd",
        )
        != projected
        or projected > ceiling
    ):
        raise ExecutionScopeError("scope cost or owner ceiling drift")
    authority = _validate_provider_authority(
        provider_authority,
        provider=entry.provider,
        projected_cost=projected,
        owner_ceiling=ceiling,
        cycle_id=cast(str, plan["cycle_id"]),
        model_key=key,
    )
    if scope.get("provider_authority") != authority:
        raise ExecutionScopeError("scope provider authority drift")
    if tuple(scope.get("selected_ablations", ())) != OFFICIAL_SCOPE_ABLATIONS:
        raise ExecutionScopeError("scope must authorize both official ablations")
    if (
        scope.get("case_count") != OFFICIAL_CASE_COUNT
        or scope.get("call_count") != OFFICIAL_CALL_COUNT
    ):
        raise ExecutionScopeError(
            "scope must authorize exactly 100 cases and 200 calls"
        )
    return actual


def select_model_scope(
    scope: Mapping[str, Any],
    *,
    model_key: str,
    ablation: str,
) -> Mapping[str, Any]:
    """Select one paid shard only when this scope authorizes it."""

    verify_scope_shape(scope)
    if scope["scope"]["model_key"] != model_key:
        raise ExecutionScopeError("scope model_key is not the selected registry model")
    if ablation not in scope["scope"]["selected_ablations"]:
        raise ExecutionScopeError("scope does not authorize selected ablation")
    return scope


def verify_scope_shape(artifact: Mapping[str, Any]) -> None:
    """Verify only the self-hash and shape, for pre-credential dispatch checks."""

    _exact_keys(artifact, {"schema_version", "scope", "scope_sha256"}, "scope artifact")
    if artifact.get("schema_version") != EXECUTION_SCOPE_SCHEMA_VERSION:
        raise ExecutionScopeError("unsupported execution scope schema")
    scope = _mapping(artifact.get("scope"), "scope")
    _exact_keys(scope, set(_SCOPE_FIELDS), "scope")
    if _sha(artifact.get("scope_sha256"), "scope_sha256") != hash_payload(scope):
        raise ExecutionScopeError("scope_sha256 does not match scope content")
    _text(scope.get("cycle_id"), "scope.cycle_id")
    _sha(scope.get("common_plan_sha256"), "scope.common_plan_sha256")
    _sha(
        scope.get("common_plan_artifact_sha256"),
        "scope.common_plan_artifact_sha256",
    )
    _validate_common_inputs(
        _mapping(scope.get("common_frozen_inputs"), "scope.common_frozen_inputs")
    )
    key = _text(scope.get("model_key"), "scope.model_key")
    if ":" not in key:
        raise ExecutionScopeError("scope.model_key must use provider:model_id")
    _sha(scope.get("registry_entry_sha256"), "scope.registry_entry_sha256")
    registry_entry = _mapping(scope.get("registry_entry"), "scope.registry_entry")
    provider = _text(registry_entry.get("provider"), "scope.registry_entry.provider")
    model_id = _text(registry_entry.get("model_id"), "scope.registry_entry.model_id")
    if key != f"{provider}:{model_id}":
        raise ExecutionScopeError("scope registry entry does not match model_key")
    if tuple(scope.get("selected_ablations", ())) != OFFICIAL_SCOPE_ABLATIONS:
        raise ExecutionScopeError("scope must authorize both official ablations")
    if (
        scope.get("case_count") != OFFICIAL_CASE_COUNT
        or scope.get("call_count") != OFFICIAL_CALL_COUNT
    ):
        raise ExecutionScopeError(
            "scope must authorize exactly 100 cases and 200 calls"
        )
    _sha(
        scope.get("cost_projection_receipt_sha256"),
        "scope.cost_projection_receipt_sha256",
    )
    projected = _money(
        _text(scope.get("projected_cost_usd"), "scope.projected_cost_usd"),
        "scope.projected_cost_usd",
    )
    ceiling = _money(
        _text(scope.get("owner_ceiling_usd"), "scope.owner_ceiling_usd"),
        "scope.owner_ceiling_usd",
    )
    if projected > ceiling:
        raise ExecutionScopeError("scope projected cost exceeds owner ceiling")
    _owner_evidence(
        _mapping(scope.get("owner_evidence"), "scope.owner_evidence"),
        model_key=key,
        projected_cost=projected,
        owner_ceiling=ceiling,
    )
    _validate_provider_authority(
        _mapping(scope.get("provider_authority"), "scope.provider_authority"),
        provider=provider,
        projected_cost=projected,
        owner_ceiling=ceiling,
        cycle_id=_text(scope.get("cycle_id"), "scope.cycle_id"),
        model_key=key,
    )


def verify_execution_scope_runtime(
    artifact: Mapping[str, Any],
    *,
    common_plan: Mapping[str, Any],
    model_registry: ModelRegistry,
    model_registry_sha256: str,
    expected_model_key: str,
    expected_ablation: str,
    expected_scope_sha256: str | None = None,
) -> str:
    """Verify scope bindings available before provider credentials are opened.

    The complete verifier also checks the private cost receipt, owner evidence,
    and provider-authority source records.  A dispatched provider cell does not
    need those source files, but it must prove that its transported scope still
    binds the selected plan, registry entry, model, and ablation first.
    """

    verify_scope_shape(artifact)
    scope = _mapping(artifact["scope"], "scope")
    plan_digest = verify_execution_policy_v3(common_plan)
    if scope.get("common_plan_sha256") != plan_digest:
        raise ExecutionScopeError("scope common plan digest drift")
    if scope.get("common_plan_artifact_sha256") != hash_payload(common_plan):
        raise ExecutionScopeError("scope common plan artifact drift")
    plan = _mapping(common_plan["policy"], "common plan policy")
    if scope.get("cycle_id") != plan.get("cycle_id"):
        raise ExecutionScopeError("scope cycle_id does not match common plan")
    key = _text(scope.get("model_key"), "model_key")
    if key != _text(expected_model_key, "expected_model_key"):
        raise ExecutionScopeError("scope model_key is not the selected model")
    if expected_ablation not in scope.get("selected_ablations", ()):
        raise ExecutionScopeError("scope does not authorize selected ablation")
    if scope.get("common_frozen_inputs") != plan.get("common_frozen_inputs"):
        raise ExecutionScopeError("scope common frozen inputs drift")
    if scope["common_frozen_inputs"].get("model_registry_sha256") != _sha(
        model_registry_sha256, "model_registry_sha256"
    ):
        raise ExecutionScopeError("scope model registry hash drift")
    entry = _registry_entry(model_registry, key)
    if (
        scope.get("registry_entry_sha256") != model_registry_entry_sha256(entry)
        or scope.get("registry_entry") != entry.to_record()
    ):
        raise ExecutionScopeError("scope registry entry drift")
    _require_plan_registry_entry(plan, key, entry)
    if (
        scope.get("selected_ablations") != list(OFFICIAL_SCOPE_ABLATIONS)
        or scope.get("case_count") != OFFICIAL_CASE_COUNT
        or scope.get("call_count") != OFFICIAL_CALL_COUNT
    ):
        raise ExecutionScopeError(
            "scope must authorize both official ablations and exactly "
            "100 cases/200 calls"
        )
    if expected_scope_sha256 is not None and artifact.get("scope_sha256") != _sha(
        expected_scope_sha256, "expected_scope_sha256"
    ):
        raise ExecutionScopeError("scope digest does not match dispatch commitment")
    return cast(str, artifact["scope_sha256"])


def compose_model_scopes(
    scopes: Sequence[Mapping[str, Any]],
    *,
    plan: Mapping[str, Any],
    model_keys: Sequence[str] | None = None,
) -> tuple[Mapping[str, Any], ...]:
    """Require one authorized scope per model while allowing two shards/scope."""

    plan_digest = verify_execution_policy_v3(plan)
    policy = _mapping(plan["policy"], "plan policy")
    declared = tuple(
        model_keys
        or sorted(_mapping(policy["model_registry_entries"], "plan registry entries"))
    )
    by_model: dict[str, Mapping[str, Any]] = {}
    for artifact in scopes:
        verify_scope_shape(artifact)
        scope = _mapping(artifact["scope"], "scope")
        key = _text(scope.get("model_key"), "scope.model_key")
        if key not in declared:
            raise ExecutionScopeError(f"scope model is unauthorized by plan: {key}")
        if key in by_model:
            raise ExecutionScopeError(f"duplicate model scope: {key}")
        if scope.get("common_plan_sha256") != plan_digest:
            raise ExecutionScopeError("scope does not belong to supplied plan")
        if scope.get("common_plan_artifact_sha256") != hash_payload(plan):
            raise ExecutionScopeError("scope does not bind the supplied plan artifact")
        plan_entry = _mapping(
            _mapping(policy.get("model_registry_entries"), "plan registry entries").get(
                key
            ),
            f"plan registry entry {key}",
        )
        registry_entry = _mapping(scope.get("registry_entry"), "scope registry entry")
        if (
            plan_entry.get("registry_entry_sha256")
            != scope.get("registry_entry_sha256")
            or plan_entry.get("registry_entry") != registry_entry
        ):
            raise ExecutionScopeError(
                "scope registry entry does not match supplied plan"
            )
        by_model[key] = artifact
    missing = sorted(set(declared) - set(by_model))
    if missing:
        raise ExecutionScopeError(f"missing model scopes: {missing}")
    return tuple(by_model[key] for key in sorted(declared))


def _validate_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    value = json.loads(json.dumps(plan, sort_keys=True, separators=(",", ":")))
    if not isinstance(value, dict):
        raise ExecutionScopeError("plan must be an object")
    normalized = cast(dict[str, Any], value)
    _exact_keys(normalized, set(_PLAN_FIELDS), "plan")
    _text(normalized.get("cycle_id"), "cycle_id")
    if normalized.get("cycle_series") != "official":
        raise ExecutionScopeError("v3 plan cycle_series must be official")
    if normalized.get("authorization_mode") != "model_scope_required":
        raise ExecutionScopeError("v3 plan must require model scopes")
    if normalized.get("provider_execution_authorized") is not False:
        raise ExecutionScopeError("v3 plan cannot authorize provider execution")
    if normalized.get("model_scope_required") is not True:
        raise ExecutionScopeError("v3 plan must require model scopes")
    _validate_common_inputs(
        _mapping(normalized.get("common_frozen_inputs"), "common_frozen_inputs")
    )
    entries = _mapping(
        normalized.get("model_registry_entries"), "model_registry_entries"
    )
    if not entries:
        raise ExecutionScopeError("plan must contain at least one model registry entry")
    for key, raw in entries.items():
        if ":" not in key:
            raise ExecutionScopeError("plan model keys must be provider:model_id")
        entry = _mapping(raw, f"model_registry_entries.{key}")
        _sha(entry.get("registry_entry_sha256"), f"registry_entry_sha256 for {key}")
        if not isinstance(entry.get("registry_entry"), Mapping):
            raise ExecutionScopeError(f"registry_entry is required for {key}")
    schedule = _mapping(normalized.get("shard_schedule"), "shard_schedule")
    if (
        set(schedule) != {"shard_count", "dispatch_unit", "shards"}
        or schedule.get("dispatch_unit") != "model_key_ablation"
    ):
        raise ExecutionScopeError("plan shard schedule is not model_key_ablation")
    raw_shards = schedule.get("shards")
    if not isinstance(raw_shards, list):
        raise ExecutionScopeError("plan shard schedule must contain shards")
    shards = cast(list[object], raw_shards)
    expected = {
        (key, ablation) for key in entries for ablation in OFFICIAL_SCOPE_ABLATIONS
    }
    actual = {
        (
            _text(_mapping(row, "shard").get("model_key"), "shard.model_key"),
            _text(_mapping(row, "shard").get("ablation"), "shard.ablation"),
        )
        for row in shards
    }
    if actual != expected or schedule.get("shard_count") != len(shards):
        raise ExecutionScopeError(
            "plan shard schedule must cover every model and ablation exactly once"
        )
    repeat = _mapping(normalized.get("repeat_policy"), "repeat_policy")
    if repeat != {"case_ids": [], "count": 1}:
        raise ExecutionScopeError("v3 plan requires repeat_count=1")
    receipt = _mapping(normalized.get("receipt_policy"), "receipt_policy")
    if receipt != {
        "write_once_per_attempt": True,
        "scope_required": True,
        "result_commitment_required": True,
    }:
        raise ExecutionScopeError("v3 plan receipt policy is not scope-bound")
    concurrency = _mapping(normalized.get("concurrency_policy"), "concurrency_policy")
    if concurrency != {
        "mode": "shard_identity",
        "identity_fields": ["cycle_id", "model_key", "ablation"],
    }:
        raise ExecutionScopeError("v3 plan concurrency policy is not shard identity")
    if _mapping(normalized.get("attempt_policy"), "attempt_policy") != {
        "scope_required": True
    }:
        raise ExecutionScopeError("v3 plan attempt policy is not scope-bound")
    return normalized


def _verify_cost_receipt(
    receipt: Mapping[str, Any], *, cycle_id: str, model_key: str
) -> str:
    supplied = _sha(receipt.get("receipt_sha256"), "cost receipt receipt_sha256")
    without = dict(receipt)
    without.pop("receipt_sha256", None)
    if hash_payload(without) != supplied:
        raise ExecutionScopeError("cost projection receipt hash does not match bytes")
    if receipt.get("cycle_id") != cycle_id:
        raise ExecutionScopeError("cost projection cycle_id does not match plan")
    if receipt.get("requested_model_keys") != [model_key] or receipt.get(
        "requested_ablations"
    ) != list(OFFICIAL_SCOPE_ABLATIONS):
        raise ExecutionScopeError(
            "cost receipt is not the exact selected-model two-ablation projection"
        )
    if (
        receipt.get("case_count") != OFFICIAL_CASE_COUNT
        or receipt.get("packet_count") != OFFICIAL_CALL_COUNT
        or receipt.get("request_count") != OFFICIAL_CALL_COUNT
        or receipt.get("attempt_count") != OFFICIAL_CALL_COUNT
    ):
        raise ExecutionScopeError(
            "cost receipt must cover exactly 100 cases and 200 calls"
        )
    if (
        receipt.get("cell_count") != 2
        or receipt.get("matrix_row_count") != OFFICIAL_CALL_COUNT
    ):
        raise ExecutionScopeError(
            "cost receipt must contain two 100-row ablation cells"
        )
    if not isinstance(receipt.get("projected_model_cost_usd"), str):
        raise ExecutionScopeError("cost receipt projected_model_cost_usd is required")
    return supplied


def _owner_evidence(
    value: Path | Mapping[str, Any] | bytes,
    *,
    model_key: str,
    projected_cost: Decimal,
    owner_ceiling: Decimal,
    expected_bead_id: str | None = None,
) -> dict[str, Any]:
    if isinstance(value, Path):
        raw = _read_bytes(value, "owner Beads evidence")
        record = _parse_owner_observation(raw)
    elif isinstance(value, bytes):
        record = _parse_owner_observation(value)
    else:
        record = dict(_mapping(value, "owner_evidence"))
        encoded = _text(
            record.get("raw_observation_base64"),
            "owner_evidence.raw_observation_base64",
        )
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as exc:
            raise ExecutionScopeError(
                "owner_evidence.raw_observation_base64 is invalid"
            ) from exc
        if _sha256_bytes(raw) != _sha(
            record.get("raw_observation_sha256"),
            "owner_evidence.raw_observation_sha256",
        ):
            raise ExecutionScopeError("owner Beads observation bytes drift")
        replayed = _parse_owner_observation(raw)
        if record != replayed:
            raise ExecutionScopeError(
                "owner evidence does not replay from raw Beads observation"
            )
    if record["model_key"] != model_key:
        raise ExecutionScopeError("owner Beads approval model differs from scope")
    if expected_bead_id is not None and record["bead_id"] != _text(
        expected_bead_id, "expected_bead_id"
    ):
        raise ExecutionScopeError("owner Beads approval issue differs from scope")
    approval_ceiling = _money(record["ceiling_usd"], "owner approval ceiling")
    approval_estimate = _money(record["estimate_usd"], "owner approval estimate")
    if approval_ceiling != owner_ceiling:
        raise ExecutionScopeError("owner ceiling does not match Beads approval")
    if approval_estimate < projected_cost:
        raise ExecutionScopeError("owner approval estimate is below projected cost")
    return {key: record[key] for key in sorted(record)}


def _parse_owner_observation(payload: bytes) -> dict[str, Any]:
    """Replay an exact raw ``bd comments <bead> --json`` observation."""

    try:
        loaded: object = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExecutionScopeError("owner Beads observation is not JSON") from exc
    if not isinstance(loaded, list):
        raise ExecutionScopeError("owner Beads observation must be a comment array")
    candidates: list[dict[str, str]] = []
    for raw_comment in cast(list[object], loaded):
        comment = _mapping(raw_comment, "owner Beads comment")
        _exact_keys(comment, set(_OWNER_COMMENT_FIELDS), "owner Beads comment")
        normalized = {
            field: _text(comment.get(field), f"owner Beads comment.{field}")
            for field in _OWNER_COMMENT_FIELDS
        }
        _owner_timestamp(normalized["created_at"])
        if normalized["author"] != "John Hughes":
            continue
        match = _OWNER_APPROVAL.fullmatch(normalized["text"])
        if match is None:
            continue
        ceiling = _owner_money(match.group("ceiling"), "owner approval ceiling")
        estimate = _owner_money(match.group("estimate"), "owner approval estimate")
        if estimate > ceiling:
            raise ExecutionScopeError("owner Beads approval estimate exceeds ceiling")
        normalized["model_key"] = match.group("model")
        normalized["ceiling_usd"] = _format_money(ceiling)
        normalized["estimate_usd"] = _format_money(estimate)
        candidates.append(normalized)
    if not candidates:
        raise ExecutionScopeError(
            "owner Beads observation lacks an exact model-scoped approval comment"
        )
    selected = max(candidates, key=lambda comment: comment["created_at"])
    comment_text = selected["text"]
    evidence = {
        "bead_id": selected["issue_id"],
        "comment_id": selected["id"],
        "author": selected["author"],
        "created_at": selected["created_at"],
        "raw_comment": comment_text,
        "raw_comment_sha256": _sha256_bytes(comment_text.encode("utf-8")),
        "raw_observation_sha256": _sha256_bytes(payload),
        "raw_observation_base64": base64.b64encode(payload).decode("ascii"),
        "model_key": selected["model_key"],
        "ceiling_usd": selected["ceiling_usd"],
        "estimate_usd": selected["estimate_usd"],
    }
    return {key: evidence[key] for key in sorted(evidence)}


def _owner_money(value: str, label: str) -> Decimal:
    if _OWNER_USD.fullmatch(value) is None:
        raise ExecutionScopeError(f"{label} must be a non-negative cent amount")
    return _money(value, label)


def _owner_timestamp(value: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExecutionScopeError(
            "owner Beads comment.created_at must be ISO-8601"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ExecutionScopeError(
            "owner Beads comment.created_at must be timezone-aware"
        )


def _validate_provider_authority(
    value: Mapping[str, Any],
    *,
    provider: str,
    projected_cost: Decimal,
    owner_ceiling: Decimal,
    cycle_id: str,
    model_key: str,
) -> dict[str, Any]:
    record = dict(value)
    expected = {
        "backend",
        "resource_identity_sha256",
        "provider",
        "account",
        "cap_microusd",
    }
    if set(record) not in (expected, expected | {"scope_identity_sha256"}):
        _exact_keys(record, expected | {"scope_identity_sha256"}, "provider_authority")
    if record.get("backend") != "dynamodb":
        raise ExecutionScopeError("provider authority backend must be dynamodb")
    _sha(
        record.get("resource_identity_sha256"),
        "provider_authority.resource_identity_sha256",
    )
    if (
        _text(record.get("provider"), "provider_authority.provider").lower()
        != provider.lower()
    ):
        raise ExecutionScopeError("provider authority provider does not match registry")
    _text(record.get("account"), "provider_authority.account")
    cap = record.get("cap_microusd")
    if not isinstance(cap, int) or isinstance(cap, bool) or cap <= 0:
        raise ExecutionScopeError("provider authority cap_microusd must be positive")
    if Decimal(cap) / Decimal(1_000_000) < projected_cost:
        raise ExecutionScopeError("provider authority cap is below projected cost")
    owner_cap_microusd = _microusd(owner_ceiling, "owner_ceiling_usd")
    if cap > owner_cap_microusd:
        raise ExecutionScopeError(
            "provider authority cap exceeds the model owner ceiling"
        )
    record["provider"] = cast(str, record["provider"]).lower()
    derived_scope_identity = hash_payload(
        {
            "cycle_id": cycle_id,
            "model_key": model_key,
            "provider": record["provider"],
            "account": record["account"],
            "resource_identity_sha256": record["resource_identity_sha256"],
            "cap_microusd": record["cap_microusd"],
            "projected_cost_usd": _format_money(projected_cost),
            "owner_ceiling_usd": _format_money(owner_ceiling),
        }
    )
    if (
        "scope_identity_sha256" in record
        and record["scope_identity_sha256"] != derived_scope_identity
    ):
        raise ExecutionScopeError(
            "provider authority scope identity does not match model scope"
        )
    record["scope_identity_sha256"] = derived_scope_identity
    return record


def _official_registry(payload: bytes) -> ModelRegistry:
    try:
        return ModelRegistry(
            require_official_registry_entries(
                load_model_registry_bytes(payload).entries
            )
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ExecutionScopeError(f"model registry is not official: {exc}") from exc


def _registry_entry(registry: ModelRegistry, model_key: str) -> ModelRegistryEntry:
    provider, separator, model_id = model_key.partition(":")
    if separator != ":" or not provider or not model_id or ":" in model_id:
        raise ExecutionScopeError("model_key must use provider:model_id")
    return registry.get(provider, model_id)


def _require_plan_registry_entry(
    plan: Mapping[str, Any], model_key: str, entry: ModelRegistryEntry
) -> None:
    """Require the selected scope model to be the exact plan registry entry."""

    entries = _mapping(plan.get("model_registry_entries"), "plan registry entries")
    plan_entry = _mapping(entries.get(model_key), f"plan registry entry {model_key}")
    if (
        plan_entry.get("registry_entry_sha256") != model_registry_entry_sha256(entry)
        or plan_entry.get("registry_entry") != entry.to_record()
    ):
        raise ExecutionScopeError("scope registry entry does not match common plan")


def load_model_registry_bytes(payload: bytes) -> ModelRegistry:
    from legalforecast.evals.model_registry import load_model_registry_bytes as load

    return load(payload)


def _load_json_source(value: Path | Mapping[str, Any], label: str) -> Mapping[str, Any]:
    if isinstance(value, Path):
        raw = _read_bytes(value, label)
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ExecutionScopeError(f"{label} is not valid JSON") from exc
    else:
        decoded = value
    return _mapping(decoded, label)


def _write_json_create_only(path: Path, value: Mapping[str, Any]) -> None:
    try:
        write_file_create_only(
            path,
            canonical_json_bytes(
                value,
                error_type=ExecutionScopeError,
                error_message="artifact is not canonical JSON",
            ),
        )
    except ImmutableIOError as exc:
        raise ExecutionScopeError(str(exc)) from exc


def _read_bytes(path: Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ExecutionScopeError(f"cannot read {label}: {path}") from exc


def _validate_common_inputs(value: Mapping[str, Any]) -> None:
    _exact_keys(value, set(_COMMON_INPUT_FIELDS), "common_frozen_inputs")
    for field in _COMMON_INPUT_FIELDS:
        _sha(value.get(field), f"common_frozen_inputs.{field}")


def _content_hash(value: Mapping[str, Any]) -> str:
    return hash_payload(value)


def _sha256_bytes(payload: bytes) -> str:
    return str(
        RAW_BYTES_RAW_SHA256_V1.commit(
            payload,
            domain=RAW_BYTES_RAW_SHA256_COMMITMENT_V1,
        ).digest
    )


def _sha(value: Any, label: str) -> str:
    text = _text(value, label)
    if _SHA256.fullmatch(text) is None:
        raise ExecutionScopeError(f"{label} must be a lowercase SHA-256")
    return text


def _money(value: str, label: str) -> Decimal:
    if _USD.fullmatch(value) is None:
        raise ExecutionScopeError(f"{label} must be a non-negative cent amount")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ExecutionScopeError(f"{label} must be decimal USD") from exc
    if not parsed.is_finite():
        raise ExecutionScopeError(f"{label} must be finite USD")
    return parsed


def _microusd(value: Decimal, label: str) -> int:
    scaled = value * Decimal(1_000_000)
    if scaled != scaled.to_integral_value():
        raise ExecutionScopeError(f"{label} cannot be represented in micro-USD")
    return int(scaled)


def _format_money(value: Decimal) -> str:
    # Cost projections are emitted at six-decimal precision.  Preserve the
    # exact finite decimal representation instead of rounding it to cents;
    # the scope must bind the receipt's projected amount byte-for-byte by
    # value, while owner ceilings may still be ordinary cent amounts.
    return format(value, "f")


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExecutionScopeError(f"{label} must be a non-empty string")
    return value.strip()


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ExecutionScopeError(f"{label} must be an object")
    return cast(Mapping[str, Any], value)


def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise ExecutionScopeError(
            f"{label} fields mismatch: missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


__all__ = [
    "EXECUTION_POLICY_V3_SCHEMA_VERSION",
    "EXECUTION_SCOPE_SCHEMA_VERSION",
    "ExecutionScopeError",
    "compose_model_scopes",
    "generate_execution_policy_v3",
    "issue_execution_plan",
    "issue_model_execution_scope",
    "select_model_scope",
    "verify_execution_policy_v3",
    "verify_execution_scope",
    "verify_execution_scope_runtime",
    "verify_scope_shape",
]
