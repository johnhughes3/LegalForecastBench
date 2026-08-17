"""Provider-free rehearsal of everything the executor checks before spending.

Issuing a spec the executor will refuse burns an owner authorization window on a
structural halt.  This module rehearses the refusal first, using the executor's
own verifiers rather than a restatement of their rules: the same lineage
verification, the same repair-receipt replay, the same provider binding, and the
same replay planner.  It opens no provider and writes nothing.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import cast

from legalforecast.ingestion.candidate_scoped_stage_a_replay import (
    bind_predecessor_stage_a_lineage,
    plan_candidate_scoped_stage_a_replay,
)
from legalforecast.ingestion.stage_a_replay_executor.contract import (
    StageAReplayExecutorError,
)
from legalforecast.ingestion.stage_a_replay_executor.contract import (
    candidate_ids_value as _candidate_ids,
)
from legalforecast.ingestion.stage_a_replay_executor.contract import (
    parse_decimal as _parse_decimal,
)
from legalforecast.ingestion.stage_a_replay_executor.lineage import (
    verify_replay_lineage,
)
from legalforecast.ingestion.stage_a_replay_executor.provider import (
    CanonicalProviderRuntime,
)
from legalforecast.ingestion.stage_a_replay_executor.spec import (
    REVIEWER_CONFIG_NAMESPACE,
    UNITIZER_CONFIG_NAMESPACE,
    ReplaySpec,
)

__all__ = ("ReplayPreflightResult", "preflight_replay_descriptor")


@dataclass(frozen=True, slots=True)
class ReplayPreflightResult:
    """What a provider-free rehearsal of the signed execution path proved."""

    accepted: bool
    stage: str
    reason: str | None
    evidence: Mapping[str, object]


def preflight_replay_descriptor(
    descriptor: Mapping[str, object],
) -> ReplayPreflightResult:
    """Rehearse lineage, repair, provider binding, and planning for a descriptor.

    The result is advisory evidence for the operator and the owner.  It is never
    execution authority: the executor re-authenticates the signed spec from
    bytes, and this rehearsal deliberately runs before any signature exists.
    """

    try:
        spec = _rehearsal_spec(descriptor)
    except StageAReplayExecutorError as exc:
        return ReplayPreflightResult(
            accepted=False, stage="descriptor", reason=str(exc), evidence={}
        )

    try:
        lineage = verify_replay_lineage(spec)
    except Exception as exc:
        return ReplayPreflightResult(
            accepted=False,
            stage="lineage",
            reason=f"{type(exc).__name__}: {exc}",
            evidence={},
        )
    if lineage.unitizer_namespace != UNITIZER_CONFIG_NAMESPACE:
        return ReplayPreflightResult(
            accepted=False,
            stage="lineage",
            reason="predecessor Stage A unitizer namespace is not frozen v5",
            evidence={},
        )
    if lineage.reviewer_namespace != REVIEWER_CONFIG_NAMESPACE:
        return ReplayPreflightResult(
            accepted=False,
            stage="lineage",
            reason="predecessor Stage A reviewer namespace is not frozen v4",
            evidence={},
        )

    try:
        predecessor = bind_predecessor_stage_a_lineage(
            candidates=lineage.predecessor,
            unitizer_namespace=lineage.unitizer_namespace,
            reviewer_namespace=lineage.reviewer_namespace,
            provider_caps_sha256=spec.provider_caps_sha256,
            provider_journal_path=spec.provider_journal_path,
            selection_sha256=lineage.predecessor_selection_sha256,
            materialization_sha256=lineage.predecessor_materialization_sha256,
            parser_sha256=lineage.predecessor_parser_sha256,
        )
        plan = plan_candidate_scoped_stage_a_replay(
            predecessor=predecessor,
            successor_packets=lineage.successor,
            successor_selection_sha256=lineage.successor_selection_sha256,
            successor_materialization_sha256=(lineage.successor_materialization_sha256),
            successor_parser_sha256=lineage.successor_parser_sha256,
            unitizer_namespace=lineage.unitizer_namespace,
            reviewer_namespace=lineage.reviewer_namespace,
            provider_caps_sha256=spec.provider_caps_sha256,
            provider_journal_path=spec.provider_journal_path,
        )
    except Exception as exc:
        return ReplayPreflightResult(
            accepted=False,
            stage="plan",
            reason=f"{type(exc).__name__}: {exc}",
            evidence={},
        )
    planned = tuple(plan.rerun_candidate_ids)
    if set(planned) != set(spec.candidate_ids) or len(planned) != len(
        spec.candidate_ids
    ):
        return ReplayPreflightResult(
            accepted=False,
            stage="plan",
            reason="planned rerun candidates differ from the descriptor candidate set",
            evidence={"planned_rerun_candidate_ids": list(planned)},
        )

    try:
        CanonicalProviderRuntime(spec, lineage)
    except Exception as exc:
        return ReplayPreflightResult(
            accepted=False,
            stage="provider",
            reason=f"{type(exc).__name__}: {exc}",
            evidence={"planned_rerun_candidate_ids": list(planned)},
        )
    return ReplayPreflightResult(
        accepted=True,
        stage="complete",
        reason=None,
        evidence={
            "planned_rerun_candidate_ids": list(planned),
            "predecessor_cohort_size": len(lineage.predecessor),
            "successor_cohort_size": len(lineage.successor),
        },
    )


def _rehearsal_spec(descriptor: Mapping[str, object]) -> ReplaySpec:
    """Shape a descriptor into the verifiers' input without granting authority.

    ``synthetic_fixture`` is forced false and no authorization is present, so
    this object can drive the production verifiers but can never be mistaken for
    a loaded, signed spec.
    """

    provider = _mapping(descriptor, "provider")
    configuration = _mapping(descriptor, "configuration")
    spend = _mapping(descriptor, "spend")
    lineage = _mapping(descriptor, "lineage")
    candidate_ids = _candidate_ids(descriptor.get("candidate_ids"), "replay descriptor")
    per_candidate_raw = _mapping(spend, "per_candidate_ceiling_usd")
    reservations_raw = _mapping(spend, "invocation_reservations_usd")
    outputs = _mapping(descriptor, "outputs")
    return ReplaySpec(
        path=Path("/nonexistent/replay-descriptor.json"),
        spec_sha256="0" * 64,
        record=MappingProxyType(dict(descriptor)),
        candidate_ids=candidate_ids,
        per_candidate_ceiling_usd=MappingProxyType(
            {
                candidate_id: _parse_decimal(
                    per_candidate_raw.get(candidate_id), candidate_id
                )
                for candidate_id in candidate_ids
            }
        ),
        aggregate_ceiling_usd=_parse_decimal(
            spend.get("aggregate_ceiling_usd"), "aggregate_ceiling_usd"
        ),
        invocation_reservations_usd=MappingProxyType(
            {
                stage: _parse_decimal(reservations_raw.get(stage), stage)
                for stage in ("unitizer", "reviewer")
            }
        ),
        code_commit=_text(descriptor, "code_commit"),
        config_hashes=MappingProxyType(
            {
                stage: _text(_mapping(configuration, stage), "config_sha256")
                for stage in ("unitizer", "reviewer")
            }
        ),
        model_ids=MappingProxyType(
            {
                stage: _text(_mapping(configuration, stage), "model_id")
                for stage in ("unitizer", "reviewer")
            }
        ),
        provider_journal_path=Path(_text(provider, "journal_path")).resolve(),
        provider_caps_sha256=_text(provider, "provider_caps_sha256"),
        model_registry_sha256=_text(provider, "model_registry_sha256"),
        cycle_id=_text(lineage, "cycle_id"),
        output_paths=MappingProxyType(
            {name: Path(_text(outputs, name)) for name in outputs}
        ),
        input_paths=(),
        synthetic_fixture=False,
    )


def _mapping(record: Mapping[str, object], field: str) -> Mapping[str, object]:
    value = record.get(field)
    if not isinstance(value, Mapping):
        raise StageAReplayExecutorError(f"replay descriptor {field} must be an object")
    return cast(Mapping[str, object], value)


def _text(record: Mapping[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise StageAReplayExecutorError(
            f"replay descriptor {field} must be non-empty text"
        )
    return value
