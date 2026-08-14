"""Replayable document-need selection artifact and v2 purchase-ceiling sidecar.

The ceiling is the single approvable spend for the admitted set. This module
does not call ``legalforecast.ingestion.purchase_approval`` (that path is live
Cycle 1 and lazy-imports the CLI).
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
from typing import cast

from legalforecast.config.registry import repository_root
from legalforecast.config.types import CycleConfig
from legalforecast.contracts import RAW_BYTES_RAW_SHA256_V1
from legalforecast.contracts.schemas import RAW_BYTES_RAW_SHA256_COMMITMENT_V1
from legalforecast.document_need.costs import CaseCosts, price_case
from legalforecast.document_need.cycle_config import (
    DocumentNeedCycleView,
    document_need_view_from_cycle_config,
    format_usd,
    preflight_selector_models,
    require_activated_cycle,
)
from legalforecast.document_need.protocol import MergedCaseBuckets
from legalforecast.document_need.ranking import (
    AdmissionDecision,
    admit_cheapest,
    provenance_record,
    rank_cases,
)
from legalforecast.document_need.types import Chronology
from legalforecast.ingestion.canonical_json import canonical_json_bytes

SELECTION_SCHEMA = (
    # contract-ratchet: allow observational post-Cycle-1 document-need sidecar
    "legalforecast.document_need_selection.v1"
)
PURCHASE_CEILING_SCHEMA = (
    # contract-ratchet: allow observational post-Cycle-1 document-need sidecar
    "legalforecast.document_need_purchase_ceiling.v1"
)
_ZERO = Decimal("0.00")


class DocumentNeedArtifactError(ValueError):
    """Raised when a selection artifact cannot be built or replayed."""


@dataclass(frozen=True, slots=True)
class PurchaseCeiling:
    """One typed-confirmation ceiling for the admitted set."""

    cycle_id: str
    selection_sha256: str
    admitted_candidate_ids: tuple[str, ...]
    ceiling_usd: Decimal
    min_usd: Decimal
    target_n: int
    confirmation_phrase: str

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": PURCHASE_CEILING_SCHEMA,
            "cycle_id": self.cycle_id,
            "selection_sha256": self.selection_sha256,
            "admitted_candidate_ids": list(self.admitted_candidate_ids),
            "ceiling_usd": format_usd(self.ceiling_usd),
            "min_usd": format_usd(self.min_usd),
            "target_n": self.target_n,
            "confirmation_phrase": self.confirmation_phrase,
            "v2_mapping": (
                "Single approvable ceiling for the admitted set. Feed this "
                "ceiling into a future Cycle 2 v2 purchase-authority request; "
                "do not invoke Cycle 1 purchase_approval from this package."
            ),
        }


@dataclass(frozen=True, slots=True)
class SelectionArtifact:
    """Deterministic selection record: buckets, costs, rank, admit/reject."""

    cycle_id: str
    selector_primary: str
    selector_alternates: tuple[str, ...]
    cases: tuple[AdmissionDecision, ...]
    case_records: tuple[Mapping[str, object], ...]
    provenance: Mapping[str, object]
    sha256: str
    purchase_ceiling: PurchaseCeiling

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": SELECTION_SCHEMA,
            "cycle_id": self.cycle_id,
            "selector_model_policy": {
                "primary": self.selector_primary,
                "alternates": list(self.selector_alternates),
            },
            "cases": [_thaw_mapping(record) for record in self.case_records],
            "provenance": _thaw_mapping(self.provenance),
            "sha256": self.sha256,
            "purchase_ceiling": self.purchase_ceiling.to_record(),
        }


def build_selection_artifact(
    *,
    config: CycleConfig,
    chronologies: Sequence[Chronology],
    merged: Sequence[MergedCaseBuckets],
    cohort_target_n: int,
) -> SelectionArtifact:
    """Price, rank, admit, and seal one replayable selection artifact."""

    require_activated_cycle(config)
    preflight_selector_models(config)
    if type(cohort_target_n) is not int or cohort_target_n <= 0:
        raise DocumentNeedArtifactError("cohort_target_n must be a positive integer")
    view = document_need_view_from_cycle_config(config)
    by_id = {row.candidate_id: row for row in merged}
    chrono_by_id = {row.candidate_id: row for row in chronologies}
    if set(by_id) != set(chrono_by_id):
        raise DocumentNeedArtifactError(
            "merged verdicts and chronologies must cover the same candidates"
        )
    if len(by_id) != len(merged) or len(chrono_by_id) != len(chronologies):
        raise DocumentNeedArtifactError("duplicate candidate_id in selection inputs")
    allowed_identities = view.selector_model_policy.allowed_identities()
    for verdicts in merged:
        if verdicts.completeness_ok is False:
            raise DocumentNeedArtifactError(
                f"candidate {verdicts.candidate_id!r} failed pass-2 completeness"
            )
        entry_ids = [row.entry for row in verdicts.entries]
        if len(entry_ids) != len(set(entry_ids)):
            raise DocumentNeedArtifactError(
                f"candidate {verdicts.candidate_id!r} has duplicate entry verdicts"
            )
        _require_promotions_match_entries(verdicts)
        checks = (
            (
                "pass1",
                verdicts.pass1_model_id,
                verdicts.pass1_provider,
                verdicts.pass1_version,
            ),
            (
                "pass2",
                verdicts.pass2_model_id,
                verdicts.pass2_provider,
                verdicts.pass2_version,
            ),
        )
        for label, model_id, provider, version in checks:
            if model_id is None:
                continue
            if provider is None or version is None:
                raise DocumentNeedArtifactError(
                    f"{label} selector identity is incomplete"
                )
            identity = (provider, model_id, version)
            if identity not in allowed_identities:
                raise DocumentNeedArtifactError(
                    f"{label} selector {provider}:{model_id} "
                    f"(version={version!r}) is not in the cycle "
                    "selector-model policy"
                )
    priced: list[CaseCosts] = []
    for candidate_id in sorted(by_id):
        verdicts = by_id[candidate_id]
        buckets = {row.entry: row for row in verdicts.entries}
        priced.append(price_case(chrono_by_id[candidate_id], buckets, view))
    ranked = rank_cases(priced)
    decisions = admit_cheapest(
        ranked,
        target_n=cohort_target_n,
        spend_ceiling=view.spend_ceiling_usd,
        max_per_case=view.max_per_case_usd,
        stratification=view.case_mix_stratification,
    )
    return _seal(
        view,
        decisions,
        by_id,
        cohort_target_n=cohort_target_n,
        evaluation_registry_sha256=_evaluation_registry_digest(config),
        cycle_record=dict(config.as_public_record()),
    )


def replay_selection_artifact(
    artifact: SelectionArtifact,
    *,
    config: CycleConfig,
    chronologies: Sequence[Chronology],
    merged: Sequence[MergedCaseBuckets],
    cohort_target_n: int,
) -> SelectionArtifact:
    """Rebuild the artifact from stored buckets + current prices; detect drift."""

    rebuilt = build_selection_artifact(
        config=config,
        chronologies=chronologies,
        merged=merged,
        cohort_target_n=cohort_target_n,
    )
    if rebuilt.sha256 != artifact.sha256:
        raise DocumentNeedArtifactError(
            "selection artifact drifted on replay "
            f"(stored={artifact.sha256} rebuilt={rebuilt.sha256})"
        )
    return rebuilt


def project_purchase_ceiling(artifact: SelectionArtifact) -> PurchaseCeiling:
    """Return the sealed ceiling already bound to the selection artifact."""

    return artifact.purchase_ceiling


def _seal(
    view: DocumentNeedCycleView,
    decisions: tuple[AdmissionDecision, ...],
    merged: Mapping[str, MergedCaseBuckets],
    *,
    cohort_target_n: int,
    evaluation_registry_sha256: str,
    cycle_record: Mapping[str, object],
) -> SelectionArtifact:
    admitted = tuple(decision for decision in decisions if decision.admitted)
    ceiling = sum((row.ranked.max_cost for row in admitted), _ZERO)
    minimum = sum((row.ranked.min_cost for row in admitted), _ZERO)
    case_records = [
        _case_record(decision, merged[decision.ranked.candidate_id])
        for decision in decisions
    ]
    content = {
        "schema_version": SELECTION_SCHEMA,
        "cycle_id": view.cycle_id,
        "cohort_target_n": cohort_target_n,
        "evaluation_registry": {
            "path": view.evaluation_registry_pin,
            "sha256": evaluation_registry_sha256,
        },
        "cycle_config": dict(cycle_record),
        "selector_model_policy": {
            "primary": view.selector_model_policy.primary,
            "alternates": list(view.selector_model_policy.alternates),
            "identities": [
                {
                    "provider": item.provider,
                    "model_id": item.model_id,
                    "model_version_or_snapshot": item.model_version_or_snapshot,
                }
                for item in view.selector_model_policy.identities
            ],
        },
        "cases": case_records,
        "provenance": provenance_record(decisions),
    }
    # contract-ratchet: allow observational document-need selection digest
    digest = hashlib.sha256(
        canonical_json_bytes(
            content,
            error_type=DocumentNeedArtifactError,
            error_message="selection artifact is not canonical JSON",
        )
    ).hexdigest()
    phrase = view.typed_confirmation.phrase_template.format(
        DECISION="APPROVE",
        cycle_id=view.cycle_id,
        request_sha256=digest,
        projected_cost_usd=format_usd(ceiling),
        rule=view.ranking_policy.purchase_rule,
        target_case_count=cohort_target_n,
        session_scope_token=view.typed_confirmation.session_scope_token,
    )
    purchase = PurchaseCeiling(
        cycle_id=view.cycle_id,
        selection_sha256=digest,
        admitted_candidate_ids=tuple(row.ranked.candidate_id for row in admitted),
        ceiling_usd=ceiling,
        min_usd=minimum,
        target_n=cohort_target_n,
        confirmation_phrase=phrase,
    )
    return SelectionArtifact(
        cycle_id=view.cycle_id,
        selector_primary=view.selector_model_policy.primary,
        selector_alternates=view.selector_model_policy.alternates,
        cases=decisions,
        case_records=tuple(_freeze_mapping(row) for row in case_records),
        provenance=_freeze_mapping(cast(Mapping[str, object], content["provenance"])),
        sha256=digest,
        purchase_ceiling=purchase,
    )


def _case_record(
    decision: AdmissionDecision, merged: MergedCaseBuckets
) -> dict[str, object]:
    record = decision.to_record()
    record["pass1_model_id"] = merged.pass1_model_id
    record["pass1_provider"] = merged.pass1_provider
    record["pass1_version"] = merged.pass1_version
    record["pass2_model_id"] = merged.pass2_model_id
    record["pass2_provider"] = merged.pass2_provider
    record["pass2_version"] = merged.pass2_version
    record["completeness_ok"] = merged.completeness_ok
    record["promotions"] = [
        {
            "entry": row.entry,
            "from_bucket": row.from_bucket.value,
            "to_bucket": row.to_bucket.value,
            "rationale": row.rationale,
            "predecision_entry_cited": row.predecision_entry_cited,
        }
        for row in merged.promotions
    ]
    return record


def _require_promotions_match_entries(verdicts: MergedCaseBuckets) -> None:
    promo_ids = [row.entry for row in verdicts.promotions]
    if len(promo_ids) != len(set(promo_ids)):
        raise DocumentNeedArtifactError(
            f"candidate {verdicts.candidate_id!r} has duplicate promotions"
        )
    by_entry = {row.entry: row for row in verdicts.entries}
    for promotion in verdicts.promotions:
        existing = by_entry.get(promotion.entry)
        if existing is None:
            raise DocumentNeedArtifactError(
                f"candidate {verdicts.candidate_id!r} promotion cites "
                f"absent entry {promotion.entry}"
            )
        if existing.bucket is not promotion.to_bucket:
            raise DocumentNeedArtifactError(
                f"candidate {verdicts.candidate_id!r} promotion to "
                f"{promotion.to_bucket.value} does not match entry "
                f"{promotion.entry}"
            )


def _evaluation_registry_digest(config: CycleConfig) -> str:
    raw = Path(config.evaluation_registry.path)
    path = raw if raw.is_absolute() else repository_root() / raw
    try:
        if not path.exists() or path.is_symlink() or not path.is_file():
            raise DocumentNeedArtifactError(
                "evaluation registry pin is not a readable regular file"
            )
        payload = path.read_bytes()
    except OSError as exc:
        raise DocumentNeedArtifactError(
            "evaluation registry pin could not be read"
        ) from exc
    return str(
        RAW_BYTES_RAW_SHA256_V1.commit(
            payload, domain=RAW_BYTES_RAW_SHA256_COMMITMENT_V1
        ).digest
    )


def _freeze_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    return MappingProxyType({key: _freeze_value(item) for key, item in value.items()})


def _freeze_value(value: object) -> object:
    if isinstance(value, Mapping):
        return _freeze_mapping(cast(Mapping[str, object], value))
    if isinstance(value, list):
        items = cast(list[object], value)
        return tuple(_freeze_value(item) for item in items)
    if isinstance(value, tuple):
        items = cast(tuple[object, ...], value)
        return tuple(_freeze_value(item) for item in items)
    return value


def _thaw_mapping(value: Mapping[str, object]) -> dict[str, object]:
    return {key: _thaw_value(item) for key, item in value.items()}


def _thaw_value(value: object) -> object:
    if isinstance(value, Mapping):
        return _thaw_mapping(cast(Mapping[str, object], value))
    if isinstance(value, list):
        items = cast(list[object], value)
        return [_thaw_value(item) for item in items]
    if isinstance(value, tuple):
        items = cast(tuple[object, ...], value)
        return [_thaw_value(item) for item in items]
    return value
