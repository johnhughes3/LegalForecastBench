"""Provider-neutral execution plans and per-model official scopes.

The deferred v2 execution policy is deliberately an all-model authority.  This
module is the additive successor for official sharding: the v3 plan is a
complete, provider-free description of the frozen run and has no execution
authority; a v1 scope is the separately authenticated owner decision for one
registry model.  A provider cell must present both artifacts before it can
open credentials.
"""

from __future__ import annotations

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
    EXECUTION_POLICY_V4,
    EXECUTION_SCOPE_SUPPLEMENTARY_V1,
    EXECUTION_SCOPE_V1,
    RAW_BYTES_RAW_SHA256_COMMITMENT_V1,
)
from legalforecast.evals.corpus_manifest.cost_projector import (
    ManifestCostProjectionError,
    verify_manifest_cost_projection_receipt,
)
from legalforecast.evals.corpus_manifest.supplementary_mode import (
    require_binding_shape,
)
from legalforecast.evals.model_registry import (
    ModelRegistry,
    ModelRegistryEntry,
    model_registry_entry_sha256,
    require_official_registry_entries,
)
from legalforecast.immutable_io import ImmutableIOError, write_file_create_only
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.labeling.provider_journal import (
    ProviderJournalError,
    load_provider_cycle_caps_bytes,
)
from legalforecast.protocol.freeze import (
    FreezeProtocolError,
    FrozenArtifactName,
    verify_freeze_bundle,
)
from legalforecast.protocol.manifest import hash_payload

EXECUTION_POLICY_V3_SCHEMA_VERSION: Final = str(EXECUTION_POLICY_V3)
EXECUTION_POLICY_V4_SCHEMA_VERSION: Final = str(EXECUTION_POLICY_V4)
EXECUTION_SCOPE_SCHEMA_VERSION: Final = str(EXECUTION_SCOPE_V1)
EXECUTION_SCOPE_SUPPLEMENTARY_SCHEMA_VERSION: Final = str(
    EXECUTION_SCOPE_SUPPLEMENTARY_V1
)
OFFICIAL_SCOPE_ABLATIONS: Final = ("full_packet", "metadata_only")
OFFICIAL_CASE_COUNT: Final = 100
OFFICIAL_CALL_COUNT: Final = 200
_SHA256: Final = re.compile(r"[0-9a-f]{64}\Z")
_USD: Final = re.compile(r"[0-9]+(?:\.[0-9]+)?\Z")
_OWNER_USD: Final = re.compile(r"[0-9]+(?:\.[0-9]{1,2})?\Z")
_MACHINE_SPECIFIC: Final = re.compile(r"/work/|/home/|/Users/|s3://", re.IGNORECASE)
"""Operator detail that must never appear in a card bound for a public repo."""


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
        "allow_no_baselines",
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
_OWNER_EVIDENCE_FIELDS: Final = frozenset(
    {
        "author",
        "bead_id",
        "ceiling_usd",
        "comment_id",
        "created_at",
        "estimate_usd",
        "model_key",
        "raw_comment",
        "raw_comment_sha256",
        "raw_observation_sha256",
    }
)
"""Both cards publish the observation's digest, not its bytes.

``bd comments <bead> --json`` returns *every* comment on the approval bead, so a
``raw_observation_base64`` field carries unbounded bystander content --
empirically absolute operator paths, ``s3://`` URIs, and private addresses, all
banned by this public repository's hygiene rule -- and re-hashes the scope
whenever anyone comments.  A scope reaches S3 only through this public
repository (the operator machine cannot write to the buckets at all), as a
commit or as a workflow input echoed into public run logs, so it must be safe to
commit.  #1009 gave the supplementary card this treatment; the official card
followed once the r4 repair made it the card actually about to be committed.

``raw_comment`` is retained: it is the owner's own approval sentence, bounded by
the ``_OWNER_APPROVAL`` fullmatch and therefore public-safe, and it is the thing
being authenticated.  With ``raw_comment_sha256`` and ``raw_observation_sha256``
anyone holding the original capture -- re-derivable from the Beads server by
bead id -- can still verify the whole chain.  ``raw_observation_base64`` is
refused by name here, not merely omitted, so the payload cannot be smuggled back
in by a card that hashes correctly.
"""

_SUPPLEMENTARY_SCOPE_FIELDS: Final = _SCOPE_FIELDS | {"supplementary_binding"}
"""A supplementary scope is a distinct card, not an official one with a field.

The supplementary variant carries its own schema identifier and its own field
set, so a supplementary scope cannot be presented as an official one: the
identifier selects the expected field set, and the field set is inside the
hashed scope.
"""


def _scope_fields(*, supplementary: bool) -> set[str]:
    return set(_SUPPLEMENTARY_SCOPE_FIELDS if supplementary else _SCOPE_FIELDS)


def _scope_schema_version(*, supplementary: bool) -> str:
    if supplementary:
        return EXECUTION_SCOPE_SUPPLEMENTARY_SCHEMA_VERSION
    return EXECUTION_SCOPE_SCHEMA_VERSION


def _require_scope_lane(
    artifact: Mapping[str, Any], *, supplementary: bool
) -> Mapping[str, Any]:
    """Select the scope card by schema identifier, refusing the other lane.

    The identifier sits outside the hashed ``scope`` object, so it is checked
    together with the lane's exact field set, which is inside it: a scope cannot
    claim one lane in its identifier and carry the other lane's body.
    """

    _exact_keys(artifact, {"schema_version", "scope", "scope_sha256"}, "scope artifact")
    expected = _scope_schema_version(supplementary=supplementary)
    if artifact.get("schema_version") != expected:
        raise ExecutionScopeError(
            "execution scope schema is not the expected lane: "
            f"expected {expected}, found {artifact.get('schema_version')!r}"
        )
    scope = _mapping(artifact.get("scope"), "scope")
    _exact_keys(scope, _scope_fields(supplementary=supplementary), "scope")
    if supplementary:
        require_binding_shape(
            scope.get("supplementary_binding"),
            label="scope.supplementary_binding",
            error_type=ExecutionScopeError,
        )
    return scope


class ExecutionScopeError(ValueError):
    """Raised when a plan or model scope is incomplete or has drifted."""


def generate_execution_policy_v3(
    plan: Mapping[str, Any],
) -> dict[str, Any]:
    """Create a strict, final-freeze-bound v3 execution plan artifact."""

    normalized = _validate_plan(plan)
    return {
        "schema_version": EXECUTION_POLICY_V3_SCHEMA_VERSION,
        "policy": normalized,
        "policy_sha256": _content_hash(normalized),
    }


def generate_execution_policy_v4(
    plan: Mapping[str, Any],
) -> dict[str, Any]:
    """Create the provider-free pre-freeze successor plan artifact.

    v4 is intentionally additive.  v3 remains the already-live, final-freeze-
    bound contract; only this successor permits the final freeze commitment to
    be filled by a later model-scope artifact.
    """

    normalized = _validate_plan(plan, allow_missing_freeze=True, version="v4")
    return {
        "schema_version": EXECUTION_POLICY_V4_SCHEMA_VERSION,
        "policy": normalized,
        "policy_sha256": _content_hash(normalized),
    }


def verify_execution_policy_v3(
    artifact: Mapping[str, Any],
    *,
    expected_cycle_id: str | None = None,
    expected_sha256: str | None = None,
) -> str:
    """Verify a v3 plan and return its policy-content digest.

    The v3 contract requires a final freeze commitment.  Do not broaden this
    verifier for the pre-freeze flow; use :func:`verify_execution_policy_v4`.
    """

    return _verify_execution_policy_artifact(
        artifact,
        schema_version=EXECUTION_POLICY_V3_SCHEMA_VERSION,
        allow_missing_freeze=False,
        version="v3",
        expected_cycle_id=expected_cycle_id,
        expected_sha256=expected_sha256,
    )


def verify_execution_policy_v4(
    artifact: Mapping[str, Any],
    *,
    expected_cycle_id: str | None = None,
    expected_sha256: str | None = None,
) -> str:
    """Verify the provider-free pre-freeze v4 plan."""

    return _verify_execution_policy_artifact(
        artifact,
        schema_version=EXECUTION_POLICY_V4_SCHEMA_VERSION,
        allow_missing_freeze=True,
        version="v4",
        expected_cycle_id=expected_cycle_id,
        expected_sha256=expected_sha256,
    )


def issue_execution_plan(
    *,
    cycle_id: str,
    model_registry: Path,
    common_frozen_inputs: Mapping[str, str],
    run_card_sha256: str | None = None,
    allow_no_baselines: bool = True,
    output: Path | None = None,
) -> dict[str, Any]:
    """Issue a strict v3 plan without granting provider authority.

    ``common_frozen_inputs`` must include the final freeze commitment.  The
    explicit v4 entry point is the only supported pre-freeze issuer.
    """

    return _issue_execution_plan(
        cycle_id=cycle_id,
        model_registry=model_registry,
        common_frozen_inputs=common_frozen_inputs,
        run_card_sha256=run_card_sha256,
        allow_no_baselines=allow_no_baselines,
        output=output,
        schema_version=EXECUTION_POLICY_V3_SCHEMA_VERSION,
        allow_missing_freeze=False,
        version="v3",
    )


def issue_execution_plan_v4(
    *,
    cycle_id: str,
    model_registry: Path,
    common_frozen_inputs: Mapping[str, str],
    run_card_sha256: str | None = None,
    allow_no_baselines: bool = True,
    output: Path | None = None,
) -> dict[str, Any]:
    """Issue a provider-free pre-freeze v4 plan without authority."""

    return _issue_execution_plan(
        cycle_id=cycle_id,
        model_registry=model_registry,
        common_frozen_inputs=common_frozen_inputs,
        run_card_sha256=run_card_sha256,
        allow_no_baselines=allow_no_baselines,
        output=output,
        schema_version=EXECUTION_POLICY_V4_SCHEMA_VERSION,
        allow_missing_freeze=True,
        version="v4",
    )


def _issue_execution_plan(
    *,
    cycle_id: str,
    model_registry: Path,
    common_frozen_inputs: Mapping[str, str],
    run_card_sha256: str | None,
    allow_no_baselines: bool,
    output: Path | None,
    schema_version: str,
    allow_missing_freeze: bool,
    version: str,
) -> dict[str, Any]:
    """Build one versioned provider-free model-scope plan.

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
    _validate_common_inputs(inputs, allow_missing_freeze=allow_missing_freeze)
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
        "allow_no_baselines": allow_no_baselines,
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
    artifact = _generate_execution_policy(
        plan,
        schema_version=schema_version,
        allow_missing_freeze=allow_missing_freeze,
        version=version,
    )
    if _read_bytes(registry_path, "model registry") != registry_bytes:
        raise ExecutionScopeError("model registry changed during plan issuance")
    if output is not None:
        _write_json_create_only(Path(output), artifact)
    return artifact


def _generate_execution_policy(
    plan: Mapping[str, Any],
    *,
    schema_version: str,
    allow_missing_freeze: bool,
    version: str,
) -> dict[str, Any]:
    normalized = _validate_plan(
        plan,
        allow_missing_freeze=allow_missing_freeze,
        version=version,
    )
    return {
        "schema_version": schema_version,
        "policy": normalized,
        "policy_sha256": _content_hash(normalized),
    }


def _verify_execution_policy_artifact(
    artifact: Mapping[str, Any],
    *,
    schema_version: str,
    allow_missing_freeze: bool,
    version: str,
    expected_cycle_id: str | None,
    expected_sha256: str | None,
) -> str:
    _exact_keys(artifact, {"schema_version", "policy", "policy_sha256"}, "plan")
    if artifact.get("schema_version") != schema_version:
        raise ExecutionScopeError(f"unsupported execution policy {version} schema")
    policy = _mapping(artifact.get("policy"), "plan policy")
    actual = _content_hash(policy)
    if _sha(artifact.get("policy_sha256"), "policy_sha256") != actual:
        raise ExecutionScopeError("plan policy_sha256 does not match policy content")
    normalized = _validate_plan(
        policy,
        allow_missing_freeze=allow_missing_freeze,
        version=version,
    )
    if expected_cycle_id is not None and normalized["cycle_id"] != expected_cycle_id:
        raise ExecutionScopeError("plan cycle_id does not match expected cycle")
    if expected_sha256 is not None and actual != _sha(
        expected_sha256, "expected_sha256"
    ):
        raise ExecutionScopeError("plan digest does not match expected digest")
    return actual


def _require_public_safe_card(artifact: Mapping[str, Any]) -> None:
    """Refuse to issue a scope card carrying machine-specific detail.

    The operator machine cannot write to the results buckets, so a scope reaches
    S3 only through this public repository -- as a commit, or as a workflow
    input echoed into public run logs.  ``.agents/AGENTS.md``'s hygiene rule
    therefore applies to the card itself.

    Dropping ``raw_observation_base64`` removed the field that carried this
    content in practice, but the card still has free-text fields fed from the
    registry (``display_name``, ``pricing_source``, ``release_timestamp_source``)
    that an operator could fill with a local path.  This is a cheap,
    non-cryptographic backstop over the whole serialized card, not a
    replacement for the field-set gate: every remaining field is a digest, a
    money string, an enum, or the grammar-bounded approval sentence, so a match
    here is a defect, never a legitimate value.

    Checked at issuance only.  Verification is deliberately left alone: a gate
    here would make an already-issued card retroactively unverifiable, and a
    card that reaches a consumer is already authenticated by digest.
    """

    text = canonical_json_bytes(
        artifact,
        error_type=ExecutionScopeError,
        error_message="execution scope is not canonically serializable",
    ).decode("utf-8")
    match = _MACHINE_SPECIFIC.search(text)
    if match is not None:
        raise ExecutionScopeError(
            "execution scope carries machine-specific operational detail "
            f"({match.group(0)!r}): a scope card is committed to this public "
            "repository and must not name local filesystem paths or bucket URIs"
        )


def issue_model_execution_scope(
    *,
    common_plan: Path | Mapping[str, Any],
    model_registry: Path,
    model_key: str,
    cost_projection: Path | Mapping[str, Any],
    run_input_manifest: Path | bytes,
    owner_ceiling_usd: str,
    owner_bead_id: str,
    provider_authority: Mapping[str, Any] | None = None,
    freeze_bundle: Path | None = None,
    freeze_root: Path | None = None,
    provider_cycle_caps: Path | None = None,
    output: Path | None = None,
    supplementary: bool = False,
) -> dict[str, Any]:
    """Issue one exact-model scope against a complete v3 plan.

    The cost receipt must be the exact one-model/two-ablation 100x2 matrix.
    The scope is therefore reusable by both paid ablation shards, while no
    second model can consume it.

    ``supplementary`` selects which lane is being authorized.  It is a
    declaration, not a claim about the model: the mode must already be recorded
    in the cost receipt, which only the authenticated projector can write, and
    the resulting scope is refused by the other lane at consumption.
    """

    plan_artifact = _load_json_source(common_plan, "common plan")
    plan_digest = _verify_common_plan(plan_artifact)
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
    plan_common_inputs = _mapping(
        plan.get("common_frozen_inputs"), "common_frozen_inputs"
    )
    cost_artifact = _load_json_source(cost_projection, "cost projection receipt")
    common_inputs = _complete_common_inputs_from_cost(
        plan_common_inputs,
        cost_artifact,
    )
    caps_snapshot = _verify_final_freeze_and_provider_caps(
        freeze_bundle=freeze_bundle,
        freeze_root=freeze_root,
        provider_cycle_caps=provider_cycle_caps,
        expected_freeze_sha256=common_inputs["freeze_bundle_sha256"],
        expected_cycle_id=_text(plan.get("cycle_id"), "cycle_id"),
    )
    cost_digest = _verify_cost_receipt(
        cost_artifact,
        cycle_id=_text(plan.get("cycle_id"), "cycle_id"),
        model_key=key,
        common_frozen_inputs=common_inputs,
        registry_entry=entry.to_record(),
        run_input_manifest=run_input_manifest,
        supplementary=supplementary,
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
    from legalforecast.evals.corpus_manifest.execution_decisions import (
        capture_beads_comments,
    )

    owner_evidence = capture_beads_comments(owner_bead_id)
    evidence = _owner_evidence(
        owner_evidence,
        model_key=key,
        projected_cost=projected,
        owner_ceiling=ceiling,
        expected_bead_id=owner_bead_id,
    )
    authority = _authority_for_scope(
        provider_authority=(None if caps_snapshot is not None else provider_authority),
        provider_cycle_caps_bytes=caps_snapshot,
        provider_cycle_caps=provider_cycle_caps,
        freeze_bundle=freeze_bundle,
        freeze_root=freeze_root,
        provider=entry.provider,
        projected_cost=projected,
        owner_ceiling=ceiling,
        cycle_id=cast(str, plan["cycle_id"]),
        model_key=key,
    )
    common_inputs = dict(common_inputs)
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
    if supplementary:
        # Copied verbatim from the authenticated receipt so the scope records
        # both bindings itself rather than making a consumer re-derive them.
        # Deep-copied so the scope and the receipt cannot alias one list.
        scope["supplementary_binding"] = json.loads(
            json.dumps(
                _mapping(
                    cost_artifact.get("supplementary_binding"),
                    "cost projection supplementary_binding",
                ),
                sort_keys=True,
            )
        )
    artifact = {
        "schema_version": _scope_schema_version(supplementary=supplementary),
        "scope": scope,
        "scope_sha256": hash_payload(scope),
    }
    verify_execution_scope(
        artifact,
        common_plan=plan_artifact,
        model_registry=registry_path,
        cost_projection=cost_artifact,
        run_input_manifest=run_input_manifest,
        owner_evidence=evidence,
        provider_authority=(None if caps_snapshot is not None else authority),
        freeze_bundle=freeze_bundle,
        freeze_root=freeze_root,
        provider_cycle_caps=provider_cycle_caps,
        provider_cycle_caps_bytes=caps_snapshot,
        expected_model_key=key,
        expected_supplementary=supplementary,
    )
    _require_public_safe_card(artifact)
    if caps_snapshot is not None and provider_cycle_caps is not None:
        _require_snapshot_unchanged(
            Path(provider_cycle_caps),
            caps_snapshot,
            "provider cycle caps before scope publication",
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
    run_input_manifest: Path | bytes,
    owner_evidence: Path | Mapping[str, Any] | bytes | None = None,
    provider_authority: Mapping[str, Any] | None = None,
    freeze_bundle: Path | None = None,
    freeze_root: Path | None = None,
    provider_cycle_caps: Path | None = None,
    provider_cycle_caps_bytes: bytes | None = None,
    expected_model_key: str | None = None,
    expected_ablation: str | None = None,
    expected_supplementary: bool = False,
) -> str:
    """Verify a scope and all source bytes it authenticates.

    ``expected_supplementary`` defaults to official, so every caller that has not
    opted into the supplementary lane refuses a supplementary scope unchanged.
    """

    scope = _require_scope_lane(artifact, supplementary=expected_supplementary)
    actual = hash_payload(scope)
    if _sha(artifact.get("scope_sha256"), "scope_sha256") != actual:
        raise ExecutionScopeError("scope_sha256 does not match scope content")
    plan_artifact = _load_json_source(common_plan, "common plan")
    plan_digest = _verify_common_plan(plan_artifact)
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
    plan_common_inputs = _mapping(
        plan.get("common_frozen_inputs"), "common_frozen_inputs"
    )
    scope_common_inputs = _mapping(
        scope.get("common_frozen_inputs"), "scope.common_frozen_inputs"
    )
    _require_scope_common_inputs_match_plan(scope_common_inputs, plan_common_inputs)
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
    common_inputs = _complete_common_inputs_from_cost(
        plan_common_inputs,
        cost_artifact,
    )
    if scope_common_inputs != common_inputs:
        raise ExecutionScopeError("scope common frozen inputs drift")
    caps_snapshot = _verify_final_freeze_and_provider_caps(
        freeze_bundle=freeze_bundle,
        freeze_root=freeze_root,
        provider_cycle_caps=provider_cycle_caps,
        provider_cycle_caps_bytes=provider_cycle_caps_bytes,
        expected_freeze_sha256=common_inputs["freeze_bundle_sha256"],
        expected_cycle_id=cast(str, plan["cycle_id"]),
    )
    cost_digest = _verify_cost_receipt(
        cost_artifact,
        cycle_id=cast(str, plan["cycle_id"]),
        model_key=key,
        common_frozen_inputs=_mapping(common_inputs, "common_frozen_inputs"),
        registry_entry=entry.to_record(),
        run_input_manifest=run_input_manifest,
        supplementary=expected_supplementary,
    )
    if scope.get("cost_projection_receipt_sha256") != cost_digest:
        raise ExecutionScopeError("scope cost projection drift")
    if expected_supplementary and scope.get(
        "supplementary_binding"
    ) != cost_artifact.get("supplementary_binding"):
        raise ExecutionScopeError("scope supplementary binding drift")
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
    authority = _authority_for_scope(
        provider_authority=provider_authority,
        provider_cycle_caps_bytes=caps_snapshot,
        provider_cycle_caps=provider_cycle_caps,
        freeze_bundle=freeze_bundle,
        freeze_root=freeze_root,
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
    supplementary: bool,
) -> Mapping[str, Any]:
    """Select one paid shard only when this scope authorizes it.

    ``supplementary`` is the lane the caller is executing, and is required: the
    shard-receipt writer reaches this selector without having run the runtime
    verifier, so an inferred lane would let a wrong-lane scope burn a write-once
    receipt slot and surface only at fan-in, after the paid run.
    """

    verify_scope_shape(scope, supplementary=supplementary)
    if scope["scope"]["model_key"] != model_key:
        raise ExecutionScopeError("scope model_key is not the selected registry model")
    if ablation not in scope["scope"]["selected_ablations"]:
        raise ExecutionScopeError("scope does not authorize selected ablation")
    return scope


def verify_scope_shape(artifact: Mapping[str, Any], *, supplementary: bool) -> None:
    """Verify only the self-hash and shape, for pre-credential dispatch checks.

    The lane is always declared by the caller and never inferred from the
    artifact.  Self-inference would let a wrong-lane scope satisfy every local
    check and surface only downstream -- for the shard-receipt writer, only at
    fan-in, after the paid run.
    """

    scope = _require_scope_lane(artifact, supplementary=supplementary)
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
    if supplementary:
        binding = _mapping(
            scope.get("supplementary_binding"), "scope.supplementary_binding"
        )
        if key not in binding.get("supplementary_model_keys", ()):
            raise ExecutionScopeError(
                "scope model_key is not in the bound supplementary registry"
            )
        # The binding names the registry under evaluation; the common frozen
        # inputs commit it. Reconciled here so the two cannot diverge by issuer
        # discipline alone.
        if binding.get("supplementary_model_registry_sha256") != _mapping(
            scope.get("common_frozen_inputs"), "scope.common_frozen_inputs"
        ).get("model_registry_sha256"):
            raise ExecutionScopeError(
                "scope supplementary registry digest does not match its frozen "
                "model_registry_sha256"
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
    expected_freeze_bundle_sha256: str | None = None,
    expected_supplementary: bool = False,
) -> str:
    """Verify scope bindings available before provider credentials are opened.

    The complete verifier also checks the private cost receipt, owner evidence,
    and provider-authority source records.  A dispatched provider cell does not
    need those source files, but it must prove that its transported scope still
    binds the selected plan, registry entry, model, and ablation first.

    ``expected_supplementary`` is the lane the caller is executing.  It defaults
    to official so an unchanged official dispatch refuses a supplementary scope,
    and a supplementary dispatch refuses an official one -- the same both-way
    refusal the per-case release-anchor gate applies to the model itself.
    """

    verify_scope_shape(artifact, supplementary=expected_supplementary)
    scope = _mapping(artifact["scope"], "scope")
    plan_digest = _verify_common_plan(common_plan)
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
    plan_common_inputs = _mapping(
        plan.get("common_frozen_inputs"), "common_frozen_inputs"
    )
    scope_common_inputs = _mapping(
        scope.get("common_frozen_inputs"), "scope.common_frozen_inputs"
    )
    _require_scope_common_inputs_match_plan(scope_common_inputs, plan_common_inputs)
    scope_freeze_sha256 = _sha(
        scope_common_inputs.get("freeze_bundle_sha256"),
        "scope.common_frozen_inputs.freeze_bundle_sha256",
    )
    if expected_freeze_bundle_sha256 is not None and scope_freeze_sha256 != _sha(
        expected_freeze_bundle_sha256, "expected_freeze_bundle_sha256"
    ):
        raise ExecutionScopeError(
            "scope freeze bundle hash does not match the current freeze"
        )
    if scope_common_inputs.get("model_registry_sha256") != _sha(
        model_registry_sha256, "model_registry_sha256"
    ):
        raise ExecutionScopeError("scope model registry hash drift")
    try:
        entry = _registry_entry(model_registry, key)
    except (KeyError, ValueError, TypeError) as exc:
        raise ExecutionScopeError(
            f"selected model is missing from the model registry: {key}"
        ) from exc
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
    supplementary: bool = False,
) -> tuple[Mapping[str, Any], ...]:
    """Require one authorized scope per model while allowing two shards/scope.

    Every composed scope must belong to the one lane the caller declares.  A
    mixed set would compose official and supplementary authorizations into a
    single authority, which is exactly the blending the lane split exists to
    prevent; the default keeps a caller that has not opted in composing official
    scopes only, as before this lane existed.
    """

    plan_digest = _verify_common_plan(plan)
    policy = _mapping(plan["policy"], "plan policy")
    declared = tuple(
        model_keys
        or sorted(_mapping(policy["model_registry_entries"], "plan registry entries"))
    )
    by_model: dict[str, Mapping[str, Any]] = {}
    for artifact in scopes:
        verify_scope_shape(artifact, supplementary=supplementary)
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


def _verify_common_plan(artifact: Mapping[str, Any]) -> str:
    """Verify either live v3 or its explicit pre-freeze v4 successor."""

    schema_version = artifact.get("schema_version")
    if schema_version == EXECUTION_POLICY_V3_SCHEMA_VERSION:
        return verify_execution_policy_v3(artifact)
    if schema_version == EXECUTION_POLICY_V4_SCHEMA_VERSION:
        return verify_execution_policy_v4(artifact)
    raise ExecutionScopeError(
        "common plan must use execution policy v3 or pre-freeze v4"
    )


def _validate_plan(
    plan: Mapping[str, Any],
    *,
    allow_missing_freeze: bool = False,
    version: str = "v3",
) -> dict[str, Any]:
    value = json.loads(json.dumps(plan, sort_keys=True, separators=(",", ":")))
    if not isinstance(value, dict):
        raise ExecutionScopeError("plan must be an object")
    normalized = cast(dict[str, Any], value)
    _exact_keys(normalized, set(_PLAN_FIELDS), "plan")
    _text(normalized.get("cycle_id"), "cycle_id")
    if normalized.get("cycle_series") != "official":
        raise ExecutionScopeError(f"{version} plan cycle_series must be official")
    if normalized.get("authorization_mode") != "model_scope_required":
        raise ExecutionScopeError(f"{version} plan must require model scopes")
    if normalized.get("provider_execution_authorized") is not False:
        raise ExecutionScopeError(f"{version} plan cannot authorize provider execution")
    if normalized.get("model_scope_required") is not True:
        raise ExecutionScopeError(f"{version} plan must require model scopes")
    if not isinstance(normalized.get("allow_no_baselines"), bool):
        raise ExecutionScopeError(f"{version} plan allow_no_baselines must be Boolean")
    _validate_common_inputs(
        _mapping(normalized.get("common_frozen_inputs"), "common_frozen_inputs"),
        allow_missing_freeze=allow_missing_freeze,
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
        raise ExecutionScopeError(f"{version} plan requires repeat_count=1")
    receipt = _mapping(normalized.get("receipt_policy"), "receipt_policy")
    if receipt != {
        "write_once_per_attempt": True,
        "scope_required": True,
        "result_commitment_required": True,
    }:
        raise ExecutionScopeError(f"{version} plan receipt policy is not scope-bound")
    concurrency = _mapping(normalized.get("concurrency_policy"), "concurrency_policy")
    if concurrency != {
        "mode": "shard_identity",
        "identity_fields": ["cycle_id", "model_key", "ablation"],
    }:
        raise ExecutionScopeError(
            f"{version} plan concurrency policy is not shard identity"
        )
    if _mapping(normalized.get("attempt_policy"), "attempt_policy") != {
        "scope_required": True
    }:
        raise ExecutionScopeError(f"{version} plan attempt policy is not scope-bound")
    return normalized


def _verify_cost_receipt(
    receipt: Mapping[str, Any],
    *,
    cycle_id: str,
    model_key: str,
    common_frozen_inputs: Mapping[str, Any],
    registry_entry: Mapping[str, Any],
    run_input_manifest: Path | bytes,
    supplementary: bool = False,
) -> str:
    try:
        return verify_manifest_cost_projection_receipt(
            receipt,
            expected_cycle_id=cycle_id,
            expected_model_key=model_key,
            expected_common_frozen_inputs=common_frozen_inputs,
            expected_registry_entry=registry_entry,
            run_input_manifest=run_input_manifest,
            expected_supplementary=supplementary,
        )
    except ManifestCostProjectionError as exc:
        raise ExecutionScopeError(str(exc)) from exc


def _replay_owner_evidence(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Re-derive an owner-evidence record from its own approval line.

    The card publishes only a digest of the ``bd comments`` payload, so a holder
    of the card alone cannot replay the *selection* that produced the record.
    Everything the selected comment determines is still re-derived here -- the
    approval grammar, the model key, both money amounts, the author, the
    timestamp, and the comment's own digest -- so a published record cannot
    disagree with the approval sentence it publishes.  A holder of the captured
    payload gets the full replay by passing those bytes instead, which the
    caller compares against this record.
    """

    record = dict(_mapping(value, "owner_evidence"))
    _exact_keys(
        record,
        set(_OWNER_EVIDENCE_FIELDS),
        "owner_evidence",
    )
    for field in sorted(_OWNER_EVIDENCE_FIELDS):
        _text(record.get(field), f"owner_evidence.{field}")
    _sha(record.get("raw_observation_sha256"), "owner_evidence.raw_observation_sha256")
    comment_text = cast(str, record["raw_comment"])
    if _sha256_bytes(comment_text.encode("utf-8")) != _sha(
        record.get("raw_comment_sha256"), "owner_evidence.raw_comment_sha256"
    ):
        raise ExecutionScopeError("owner approval comment bytes drift")
    if record["author"] != "John Hughes":
        raise ExecutionScopeError("owner approval comment is not owner-authored")
    _owner_timestamp(cast(str, record["created_at"]))
    match = _OWNER_APPROVAL.fullmatch(comment_text)
    if match is None:
        raise ExecutionScopeError(
            "owner_evidence.raw_comment is not an exact model-scoped approval"
        )
    ceiling = _owner_money(match.group("ceiling"), "owner approval ceiling")
    estimate = _owner_money(match.group("estimate"), "owner approval estimate")
    if estimate > ceiling:
        raise ExecutionScopeError("owner Beads approval estimate exceeds ceiling")
    if record["model_key"] != match.group("model"):
        raise ExecutionScopeError("owner approval model does not match its approval")
    if record["ceiling_usd"] != _format_money(ceiling):
        raise ExecutionScopeError("owner approval ceiling does not match its approval")
    if record["estimate_usd"] != _format_money(estimate):
        raise ExecutionScopeError("owner approval estimate does not match its approval")
    return record


def _owner_evidence(
    value: Path | Mapping[str, Any] | bytes,
    *,
    model_key: str,
    projected_cost: Decimal,
    owner_ceiling: Decimal,
    expected_bead_id: str | None = None,
) -> dict[str, Any]:
    """Authenticate owner evidence.

    Both lanes publish the same digest-only record, so there is no lane
    parameter here: a caller holding the captured ``bd comments`` bytes gets the
    full replay by passing them, and a caller holding only the card re-derives
    every field the approval sentence determines.
    """

    if isinstance(value, Path):
        record = _parse_owner_observation(_read_bytes(value, "owner Beads evidence"))
    elif isinstance(value, bytes):
        record = _parse_owner_observation(value)
    else:
        record = _replay_owner_evidence(value)
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
    """Replay an exact raw ``bd comments <bead> --json`` observation.

    The record keeps the observation's digest, never the observation itself:
    see ``_OWNER_EVIDENCE_FIELDS``.
    """

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


def _require_snapshot_unchanged(path: Path, snapshot: bytes, label: str) -> None:
    """Reject source replacement after authenticated bytes were captured."""

    if _read_bytes(path, label) != snapshot:
        raise ExecutionScopeError(f"{label} changed after authentication")


def _validate_common_inputs(
    value: Mapping[str, Any], *, allow_missing_freeze: bool = False
) -> None:
    expected = set(_COMMON_INPUT_FIELDS)
    if allow_missing_freeze:
        actual = set(value)
        if actual == expected - {"freeze_bundle_sha256"}:
            expected.remove("freeze_bundle_sha256")
    _exact_keys(value, expected, "common_frozen_inputs")
    for field in expected:
        _sha(value.get(field), f"common_frozen_inputs.{field}")


def _require_scope_common_inputs_match_plan(
    scope_inputs: Mapping[str, Any], plan_inputs: Mapping[str, Any]
) -> None:
    """Require a scope to preserve every plan commitment it can inherit.

    A pre-freeze v4 plan intentionally omits only the final bundle hash.  The
    scope must add that hash after the final freeze is created; all other
    commitments remain byte-identical to the plan.
    """

    _validate_common_inputs(scope_inputs)
    _validate_common_inputs(plan_inputs, allow_missing_freeze=True)
    for field, value in plan_inputs.items():
        if scope_inputs.get(field) != value:
            raise ExecutionScopeError(f"scope common frozen input drift: {field}")


def _complete_common_inputs_from_cost(
    plan_inputs: Mapping[str, Any], cost_artifact: Mapping[str, Any]
) -> dict[str, Any]:
    """Complete a pre-freeze plan with the authenticated final freeze hash."""

    _validate_common_inputs(plan_inputs, allow_missing_freeze=True)
    raw_commitments_value = cost_artifact.get("input_commitments")
    if not isinstance(raw_commitments_value, Mapping):
        raise ExecutionScopeError(
            "cost projection fields mismatch: missing=['input_commitments'], unknown=[]"
        )
    raw_commitments = cast(Mapping[str, Any], raw_commitments_value)
    freeze_commitment = _mapping(
        raw_commitments.get("freeze_bundle"),
        "cost projection input_commitments.freeze_bundle",
    )
    freeze_sha256 = _sha(
        freeze_commitment.get("sha256"),
        "cost projection input_commitments.freeze_bundle.sha256",
    )
    existing = plan_inputs.get("freeze_bundle_sha256")
    if (
        existing is not None
        and _sha(existing, "common_frozen_inputs.freeze_bundle_sha256") != freeze_sha256
    ):
        raise ExecutionScopeError(
            "cost receipt freeze bundle hash does not match common plan"
        )
    completed = dict(plan_inputs)
    completed["freeze_bundle_sha256"] = freeze_sha256
    _validate_common_inputs(completed)
    return completed


def _verify_final_freeze_and_provider_caps(
    *,
    freeze_bundle: Path | None,
    freeze_root: Path | None,
    provider_cycle_caps: Path | None,
    provider_cycle_caps_bytes: bytes | None = None,
    expected_freeze_sha256: str,
    expected_cycle_id: str,
) -> bytes | None:
    """Verify the staged freeze and cap bytes used to derive authority."""

    if freeze_bundle is None and provider_cycle_caps is None:
        # Existing callers may still use the legacy injected authority API.
        if provider_cycle_caps_bytes is not None:
            raise ExecutionScopeError(
                "provider cycle caps bytes require freeze_bundle and "
                "provider_cycle_caps"
            )
        return None
    if freeze_bundle is None or (
        provider_cycle_caps is None and provider_cycle_caps_bytes is None
    ):
        raise ExecutionScopeError(
            "freeze_bundle and provider_cycle_caps are required together"
        )
    freeze_path = Path(freeze_bundle)
    freeze_bytes = _read_bytes(freeze_path, "final freeze bundle")
    if _sha256_bytes(freeze_bytes) != _sha(
        expected_freeze_sha256, "expected final freeze bundle hash"
    ):
        raise ExecutionScopeError(
            "final freeze bundle bytes do not match authenticated cost receipt"
        )
    root = Path(freeze_root) if freeze_root is not None else freeze_path.parent
    try:
        bundle = verify_freeze_bundle(
            freeze_path,
            cycle_id=expected_cycle_id,
            root_path=root,
        )
    except (FreezeProtocolError, OSError, ValueError) as exc:
        raise ExecutionScopeError(f"final freeze bundle is invalid: {exc}") from exc
    frozen_caps = bundle.artifact(FrozenArtifactName.PROVIDER_CYCLE_CAPS)
    caps_bytes = (
        provider_cycle_caps_bytes
        if provider_cycle_caps_bytes is not None
        else _read_bytes(Path(cast(Path, provider_cycle_caps)), "provider cycle caps")
    )
    if (
        _sha256_bytes(caps_bytes) != frozen_caps.sha256
        or len(caps_bytes) != frozen_caps.size_bytes
    ):
        raise ExecutionScopeError(
            "provider cycle caps bytes do not match the final freeze"
        )
    return caps_bytes


def _authority_for_scope(
    *,
    provider_authority: Mapping[str, Any] | None,
    provider_cycle_caps: Path | None,
    provider_cycle_caps_bytes: bytes | None = None,
    freeze_bundle: Path | None,
    freeze_root: Path | None,
    provider: str,
    projected_cost: Decimal,
    owner_ceiling: Decimal,
    cycle_id: str,
    model_key: str,
) -> dict[str, Any]:
    """Derive provider authority from frozen caps for the production path.

    ``provider_authority`` remains an injected compatibility seam for older
    callers and fixtures.  The supported CLI supplies the freeze and caps
    paths, in which case no caller-authored authority JSON is accepted.
    """

    if provider_cycle_caps is None and provider_cycle_caps_bytes is None:
        if provider_authority is None:
            raise ExecutionScopeError(
                "provider_cycle_caps is required to derive provider authority"
            )
        return _validate_provider_authority(
            provider_authority,
            provider=provider,
            projected_cost=projected_cost,
            owner_ceiling=owner_ceiling,
            cycle_id=cycle_id,
            model_key=model_key,
        )
    if provider_authority is not None:
        raise ExecutionScopeError(
            "caller-authored provider authority is not accepted with frozen caps"
        )
    if freeze_bundle is None:
        raise ExecutionScopeError(
            "freeze_bundle is required when deriving provider authority"
        )
    caps_path = Path(provider_cycle_caps) if provider_cycle_caps is not None else None
    caps_bytes = (
        provider_cycle_caps_bytes
        if provider_cycle_caps_bytes is not None
        else _read_bytes(cast(Path, caps_path), "provider cycle caps")
    )
    caps_source: str | Path = (
        caps_path if caps_path is not None else "authenticated provider cycle caps"
    )
    try:
        caps = load_provider_cycle_caps_bytes(caps_bytes, source=caps_source)
        authority_policy = caps.require_spend_authority()
        cap_microusd = caps.cap_microusd(provider)
        account = caps.account(provider)
    except ProviderJournalError as exc:
        raise ExecutionScopeError(f"provider cycle caps are invalid: {exc}") from exc
    if caps.cycle_id != cycle_id:
        raise ExecutionScopeError(
            "provider cycle caps cycle_id does not match common plan"
        )
    authority = {
        "backend": authority_policy.backend,
        "resource_identity_sha256": authority_policy.resource_identity_sha256,
        "provider": provider,
        "account": account,
        "cap_microusd": cap_microusd,
    }
    validated = _validate_provider_authority(
        authority,
        provider=provider,
        projected_cost=projected_cost,
        owner_ceiling=owner_ceiling,
        cycle_id=cycle_id,
        model_key=model_key,
    )
    # The caller carries the exact authenticated bytes through owner-evidence
    # capture.  Publication performs the final path recheck in the issuer,
    # after all other source work has completed.
    return validated


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
    "EXECUTION_POLICY_V4_SCHEMA_VERSION",
    "EXECUTION_SCOPE_SCHEMA_VERSION",
    "ExecutionScopeError",
    "compose_model_scopes",
    "generate_execution_policy_v3",
    "generate_execution_policy_v4",
    "issue_execution_plan",
    "issue_execution_plan_v4",
    "issue_model_execution_scope",
    "select_model_scope",
    "verify_execution_policy_v3",
    "verify_execution_policy_v4",
    "verify_execution_scope",
    "verify_execution_scope_runtime",
    "verify_scope_shape",
]
