"""Cycle-level stratified blind audit planning for unanimous Stage B labels."""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from legalforecast.labeling.label_outcomes import UnitResolution
from legalforecast.protocol.policy_artifacts import (
    PolicyArtifactError,
    labeling_policy_content,
    verify_labeling_policy,
)

JsonRecord = dict[str, Any]
PLAN_SCHEMA_VERSION = "legalforecast.cycle_label_audit_plan.v1"
QUEUE_SCHEMA_VERSION = "legalforecast.lawyer_review_queue.v1"
STRATA = ("unanimous_grant", "unanimous_deny", "partial")


class CycleLabelAuditError(ValueError):
    """Raised when cycle-level label-audit artifacts fail closed."""


@dataclass(frozen=True, slots=True)
class CycleLabelAuditPolicy:
    cycle_id: str
    judge_registry_sha256: str
    sample_fraction: float
    minimum_sample_size: int
    minimum_per_stratum: int
    max_llm_error_rate: float
    max_human_disagreement_rate: float
    policy_sha256: str

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> CycleLabelAuditPolicy:
        try:
            policy_sha256 = verify_labeling_policy(record)
            content = labeling_policy_content(record)
        except PolicyArtifactError as exc:
            raise CycleLabelAuditError(str(exc)) from exc
        section = _mapping(content.get("label_audit"), "label_audit")
        policy = cls(
            cycle_id=_required_str(content, "cycle_id"),
            judge_registry_sha256=_sha256(
                _required_str(content, "judge_registry_sha256"),
                "judge_registry_sha256",
            ),
            sample_fraction=_probability(section, "sample_fraction", positive=True),
            minimum_sample_size=_positive_int(section, "minimum_sample_size"),
            minimum_per_stratum=_positive_int(section, "minimum_per_stratum"),
            max_llm_error_rate=_probability(section, "max_llm_error_rate"),
            max_human_disagreement_rate=_probability(
                section, "max_human_disagreement_rate"
            ),
            policy_sha256=_sha256(policy_sha256, "policy_sha256"),
        )
        return policy


@dataclass(frozen=True, slots=True)
class _PopulationUnit:
    candidate_id: str
    case_id: str
    unit_id: str
    stratum: str
    auto_label: Mapping[str, Any]
    votes: tuple[Mapping[str, Any], ...]

    @property
    def identity(self) -> str:
        return f"{self.candidate_id}:{self.unit_id}"

    def commitment_record(self) -> JsonRecord:
        return {
            "candidate_id": self.candidate_id,
            "case_id": self.case_id,
            "unit_id": self.unit_id,
            "stratum": self.stratum,
            "auto_label": dict(self.auto_label),
            "votes": [dict(vote) for vote in self.votes],
        }


def plan_cycle_label_audit(
    *,
    label_audit_records: Iterable[Mapping[str, Any]],
    selection_records: Iterable[Mapping[str, Any]],
    finalized_prediction_unit_records: Iterable[Mapping[str, Any]],
    decision_text_records: Iterable[Mapping[str, Any]],
    policy_record: Mapping[str, Any],
) -> tuple[JsonRecord, tuple[JsonRecord, ...], tuple[JsonRecord, ...]]:
    """Freeze one cycle-wide sample and return plan, augmented audits, and queue."""

    policy = CycleLabelAuditPolicy.from_record(policy_record)
    audits = [dict(record) for record in label_audit_records]
    population = _population(audits)
    plan, sampled = _expected_plan(policy=policy, population=population)
    corpus_sha = cast(str, plan["ensemble_corpus_sha256"])
    sampled_by_candidate: dict[str, list[_PopulationUnit]] = defaultdict(list)
    for unit in sampled:
        sampled_by_candidate[unit.candidate_id].append(unit)

    plan_sha = _canonical_sha256(plan)
    selections: dict[str, Mapping[str, Any]] = {}
    for selection in selection_records:
        candidate_id = _required_str(selection, "candidate_id")
        if candidate_id in selections:
            raise CycleLabelAuditError(f"duplicate selection candidate: {candidate_id}")
        selections[candidate_id] = selection
    units = _units_by_candidate(finalized_prediction_unit_records)
    decision_texts: dict[str, Mapping[str, Any]] = {}
    for decision in decision_text_records:
        document_id = _required_str(decision, "document_id")
        if document_id in decision_texts:
            raise CycleLabelAuditError(f"duplicate decision text: {document_id}")
        decision_texts[document_id] = decision
    queue = tuple(
        _queue_record(
            unit,
            selection=selections[unit.candidate_id],
            prediction_unit=units[unit.candidate_id][unit.unit_id],
            decision_texts=decision_texts,
            plan_sha256=plan_sha,
        )
        for unit in sampled
    )
    augmented: list[JsonRecord] = []
    for audit in audits:
        candidate_id = _required_str(audit, "candidate_id")
        local = sampled_by_candidate.get(candidate_id, [])
        audit["label_audit_gate"] = {
            "required": True,
            "status": (
                "awaiting_human_adjudicated_labels"
                if local
                else "covered_by_cycle_level_plan"
            ),
            "cycle_level": True,
            "cycle_label_audit_plan_sha256": plan_sha,
            "ensemble_corpus_sha256": corpus_sha,
            "sample_unit_ids": [unit.unit_id for unit in local],
        }
        augmented.append(audit)
    return ({**plan, "plan_sha256": plan_sha}, tuple(augmented), queue)


def evaluate_cycle_label_audit(
    *,
    plan: Mapping[str, Any],
    label_audit_records: Iterable[Mapping[str, Any]],
    adjudications_by_review_id: Mapping[str, Mapping[str, Any]],
    policy_record: Mapping[str, Any],
) -> tuple[JsonRecord, ...]:
    """Evaluate the frozen sample without using post-adjudication label bytes."""

    if plan.get("schema_version") != PLAN_SCHEMA_VERSION:
        raise CycleLabelAuditError(f"cycle audit plan must use {PLAN_SCHEMA_VERSION}")
    plan_without_hash = dict(plan)
    claimed_plan_sha = _required_str(plan_without_hash, "plan_sha256")
    del plan_without_hash["plan_sha256"]
    if _canonical_sha256(plan_without_hash) != claimed_plan_sha:
        raise CycleLabelAuditError("cycle label audit plan hash mismatch")
    audit_rows = tuple(label_audit_records)
    population = _population(audit_rows)
    policy = CycleLabelAuditPolicy.from_record(policy_record)
    expected_plan, _ = _expected_plan(policy=policy, population=population)
    if plan_without_hash != expected_plan:
        raise CycleLabelAuditError(
            "cycle label audit plan does not match the pinned policy and corpus"
        )
    actual_corpus_sha = cast(str, expected_plan["ensemble_corpus_sha256"])
    auto_by_identity = {unit.identity: unit for unit in population}
    samples = _records(plan.get("sampled_units"), "sampled_units")
    policy = _mapping(plan.get("sampling_policy"), "sampling_policy")
    max_llm = _probability(policy, "max_llm_error_rate")
    max_human = _probability(policy, "max_human_disagreement_rate")
    metrics: dict[str, dict[str, int]] = {
        stratum: {"sample": 0, "llm_errors": 0, "human_disagreements": 0}
        for stratum in STRATA
    }
    candidate_samples: dict[str, list[str]] = defaultdict(list)
    expected_review_ids = {_required_str(sample, "review_id") for sample in samples}
    unexpected_audit_ids = sorted(
        review_id
        for review_id in adjudications_by_review_id
        if review_id.endswith(":label-audit") and review_id not in expected_review_ids
    )
    if unexpected_audit_ids:
        raise CycleLabelAuditError(
            f"unexpected cycle label audit adjudication: {unexpected_audit_ids[0]}"
        )
    for sample in samples:
        candidate_id = _required_str(sample, "candidate_id")
        unit_id = _required_str(sample, "unit_id")
        review_id = _required_str(sample, "review_id")
        identity = f"{candidate_id}:{unit_id}"
        auto = auto_by_identity.get(identity)
        if auto is None:
            raise CycleLabelAuditError(f"sampled auto label missing: {identity}")
        adjudication = adjudications_by_review_id.get(review_id)
        if adjudication is None:
            raise CycleLabelAuditError(
                f"cycle label audit missing adjudication: {review_id}"
            )
        if _required_str(adjudication, "review_id") != review_id:
            raise CycleLabelAuditError(
                f"adjudication review identity mismatch: {review_id}"
            )
        if _required_str(adjudication, "candidate_id") != candidate_id:
            raise CycleLabelAuditError(
                f"adjudication candidate identity mismatch: {review_id}"
            )
        if _required_str(adjudication, "unit_id") != unit_id:
            raise CycleLabelAuditError(
                f"adjudication unit identity mismatch: {review_id}"
            )
        adjudicated = _mapping(
            adjudication.get("adjudicated_label"), "adjudicated_label"
        )
        if _required_str(adjudicated, "unit_id") != unit_id:
            raise CycleLabelAuditError(
                f"adjudicated label unit identity mismatch: {review_id}"
            )
        stratum = _required_str(sample, "stratum")
        metric = metrics[stratum]
        metric["sample"] += 1
        metric["llm_errors"] += int(
            _label_signature(auto.auto_label) != _label_signature(adjudicated)
        )
        reviewer_responses = _records(
            adjudication.get("reviewer_responses"), "reviewer_responses"
        )
        if len(reviewer_responses) < 2:
            raise CycleLabelAuditError(
                "cycle label audit requires at least two independent human "
                f"reviewer responses: {review_id}"
            )
        for response in reviewer_responses:
            if _required_str(response, "review_id") != review_id:
                raise CycleLabelAuditError(
                    f"reviewer response identity mismatch: {review_id}"
                )
            proposed = _mapping(response.get("proposed_label"), "proposed_label")
            if _required_str(proposed, "unit_id") != unit_id:
                raise CycleLabelAuditError(
                    f"reviewer label unit identity mismatch: {review_id}"
                )
        response_signatures = {
            _label_signature(_mapping(response.get("proposed_label"), "proposed_label"))
            for response in reviewer_responses
        }
        metric["human_disagreements"] += int(len(response_signatures) > 1)
        candidate_samples[candidate_id].append(unit_id)

    strata_results: list[JsonRecord] = []
    passed = True
    plan_strata = {
        _required_str(row, "stratum"): row
        for row in _records(plan.get("strata"), "strata")
    }
    for stratum in STRATA:
        population_count = _required_int(plan_strata[stratum], "population_count")
        metric = metrics[stratum]
        sample_count = metric["sample"]
        if population_count and sample_count == 0:
            passed = False
        llm_rate = metric["llm_errors"] / sample_count if sample_count else None
        human_rate = (
            metric["human_disagreements"] / sample_count if sample_count else None
        )
        if llm_rate is not None and llm_rate > max_llm:
            passed = False
        if human_rate is not None and human_rate > max_human:
            passed = False
        strata_results.append(
            {
                "stratum": stratum,
                "population_count": population_count,
                "sample_count": sample_count,
                "llm_error_rate": llm_rate,
                "human_disagreement_rate": human_rate,
                "status": "empty" if population_count == 0 else "passed",
            }
        )
    if not passed:
        raise CycleLabelAuditError("cycle-level stratified label audit failed closed")
    candidate_ids = sorted(
        {
            _required_str(record, "candidate_id")
            for record in audit_rows
            if record.get("stage") == "llm-label" and record.get("status") != "failed"
        }
    )
    return tuple(
        {
            "schema_version": "legalforecast.cycle_label_audit_gate.v1",
            "stage": "label-audit-gate",
            "status": "passed",
            "candidate_id": candidate_id,
            "sample_unit_ids": sorted(unit_ids),
            "cycle_label_audit_plan_sha256": claimed_plan_sha,
            "ensemble_corpus_sha256": actual_corpus_sha,
            "strata": strata_results,
            "human_verified": True,
        }
        for candidate_id in candidate_ids
        for unit_ids in (candidate_samples.get(candidate_id, []),)
    )


def _expected_plan(
    *,
    policy: CycleLabelAuditPolicy,
    population: Sequence[_PopulationUnit],
) -> tuple[JsonRecord, tuple[_PopulationUnit, ...]]:
    """Reconstruct every security-relevant plan field from policy and corpus."""

    if not population:
        raise CycleLabelAuditError("cycle label audit population is empty")
    corpus_sha = _canonical_sha256([unit.commitment_record() for unit in population])
    seed = hashlib.sha256(
        f"{policy.cycle_id}\0{corpus_sha}\0{policy.policy_sha256}".encode()
    ).hexdigest()
    sample_size = min(
        len(population),
        max(
            policy.minimum_sample_size,
            math.ceil(policy.sample_fraction * len(population)),
        ),
    )
    allocation = _allocate_sample(population, sample_size, policy.minimum_per_stratum)
    sampled = _sample_population(population, allocation=allocation, seed=seed)
    return (
        {
            "schema_version": PLAN_SCHEMA_VERSION,
            "cycle_id": policy.cycle_id,
            "judge_registry_sha256": policy.judge_registry_sha256,
            "labeling_policy_sha256": policy.policy_sha256,
            "ensemble_corpus_sha256": corpus_sha,
            "seed_sha256": seed,
            "population_count": len(population),
            "sample_count": len(sampled),
            "sampling_policy": {
                "sample_fraction": policy.sample_fraction,
                "minimum_sample_size": policy.minimum_sample_size,
                "minimum_per_stratum": policy.minimum_per_stratum,
                "max_llm_error_rate": policy.max_llm_error_rate,
                "max_human_disagreement_rate": policy.max_human_disagreement_rate,
            },
            "strata": [
                {
                    "stratum": stratum,
                    "population_count": sum(
                        1 for unit in population if unit.stratum == stratum
                    ),
                    "sample_count": allocation.get(stratum, 0),
                }
                for stratum in STRATA
            ],
            "sampled_units": [
                {
                    "candidate_id": unit.candidate_id,
                    "case_id": unit.case_id,
                    "unit_id": unit.unit_id,
                    "stratum": unit.stratum,
                    "review_id": f"{unit.candidate_id}:{unit.unit_id}:label-audit",
                    "auto_label_sha256": _canonical_sha256(unit.auto_label),
                }
                for unit in sampled
            ],
        },
        sampled,
    )


def _population(records: Iterable[Mapping[str, Any]]) -> tuple[_PopulationUnit, ...]:
    output: list[_PopulationUnit] = []
    identities: set[str] = set()
    for audit in records:
        if audit.get("stage") != "llm-label" or audit.get("status") == "failed":
            continue
        candidate_id = _required_str(audit, "candidate_id")
        case_id = _required_str(audit, "case_id")
        ensemble = _mapping(audit.get("ensemble"), "ensemble")
        for decision in _records(ensemble.get("decisions"), "decisions"):
            if decision.get("status") != "auto_label":
                continue
            label = _mapping(decision.get("unanimous_label"), "unanimous_label")
            unit = _PopulationUnit(
                candidate_id=candidate_id,
                case_id=case_id,
                unit_id=_required_str(decision, "unit_id"),
                stratum=_stratum(label),
                auto_label=label,
                votes=_records(decision.get("votes"), "votes"),
            )
            if unit.identity in identities:
                raise CycleLabelAuditError(
                    f"duplicate cycle audit unit: {unit.identity}"
                )
            identities.add(unit.identity)
            output.append(unit)
    return tuple(sorted(output, key=lambda unit: unit.identity))


def _allocate_sample(
    population: Sequence[_PopulationUnit], sample_size: int, minimum: int
) -> dict[str, int]:
    sizes = {s: sum(1 for unit in population if unit.stratum == s) for s in STRATA}
    if sample_size == len(population):
        return sizes
    allocation = {s: min(minimum, sizes[s]) for s in STRATA}
    remaining = sample_size - sum(allocation.values())
    if remaining < 0:
        raise CycleLabelAuditError("sample size cannot satisfy per-stratum minimum")
    capacities = {s: sizes[s] - allocation[s] for s in STRATA}
    capacity_total = sum(capacities.values())
    if remaining and capacity_total:
        ideals = {s: remaining * capacities[s] / capacity_total for s in STRATA}
        for s in STRATA:
            allocation[s] += min(capacities[s], math.floor(ideals[s]))
        left = sample_size - sum(allocation.values())
        order = sorted(
            STRATA,
            key=lambda s: (ideals[s] - math.floor(ideals[s]), s),
            reverse=True,
        )
        for s in order:
            if left and allocation[s] < sizes[s]:
                allocation[s] += 1
                left -= 1
    if sum(allocation.values()) != sample_size:
        raise CycleLabelAuditError("largest-remainder allocation did not reconcile")
    return allocation


def _sample_population(
    population: Sequence[_PopulationUnit], *, allocation: Mapping[str, int], seed: str
) -> tuple[_PopulationUnit, ...]:
    by_stratum: dict[str, list[_PopulationUnit]] = defaultdict(list)
    for unit in population:
        by_stratum[unit.stratum].append(unit)
    selected: list[_PopulationUnit] = []
    for stratum in STRATA:
        ranked = sorted(
            by_stratum[stratum],
            key=lambda unit: hashlib.sha256(
                f"{seed}:{unit.identity}".encode()
            ).hexdigest(),
        )
        selected.extend(ranked[: allocation.get(stratum, 0)])
    return tuple(sorted(selected, key=lambda unit: unit.identity))


def _queue_record(
    unit: _PopulationUnit,
    *,
    selection: Mapping[str, Any],
    prediction_unit: Mapping[str, Any],
    decision_texts: Mapping[str, Mapping[str, Any]],
    plan_sha256: str,
) -> JsonRecord:
    document_id = _decision_document_id(selection)
    decision = decision_texts.get(document_id)
    if decision is None:
        raise CycleLabelAuditError(f"decision text missing for {document_id}")
    review_id = f"{unit.candidate_id}:{unit.unit_id}:label-audit"
    packet = {
        "review_id": review_id,
        "candidate_id": unit.candidate_id,
        "unit_id": unit.unit_id,
        "audience": "label_reviewer",
        "blind_reliability_study": True,
        "review_reason": "label_audit_sample",
        "contains_decision_material": True,
        "materials": [
            {
                "material_id": f"{unit.unit_id}:frozen-unit",
                "kind": "unit_text",
                "text": json.dumps(prediction_unit, sort_keys=True),
                "source_document_id": None,
                "source_hash": None,
                "is_decision_material": False,
            },
            {
                "material_id": f"{unit.unit_id}:first-written-disposition",
                "kind": "decision_excerpt",
                "text": _required_str(decision, "text"),
                "source_document_id": document_id,
                "source_hash": None,
                "is_decision_material": True,
            },
        ],
    }
    return {
        "schema_version": QUEUE_SCHEMA_VERSION,
        "status": "pending_adjudication",
        "candidate_id": unit.candidate_id,
        "case_id": unit.case_id,
        "unit_id": unit.unit_id,
        "review_id": review_id,
        "route_reason": "label_audit_sample",
        "cycle_label_audit_plan_sha256": plan_sha256,
        "packet": packet,
    }


def _units_by_candidate(
    records: Iterable[Mapping[str, Any]],
) -> dict[str, dict[str, Mapping[str, Any]]]:
    result: dict[str, dict[str, Mapping[str, Any]]] = {}
    for record in records:
        if record.get("status") == "candidate_excluded":
            continue
        candidate_id = _required_str(record, "candidate_id")
        if candidate_id in result:
            raise CycleLabelAuditError(
                f"duplicate prediction-unit candidate: {candidate_id}"
            )
        candidate_units: dict[str, Mapping[str, Any]] = {}
        for unit in _records(record.get("prediction_units"), "prediction_units"):
            unit_id = _required_str(unit, "unit_id")
            if unit_id in candidate_units:
                raise CycleLabelAuditError(
                    f"duplicate prediction unit: {candidate_id}:{unit_id}"
                )
            candidate_units[unit_id] = unit
        result[candidate_id] = candidate_units
    return result


def _decision_document_id(selection: Mapping[str, Any]) -> str:
    documents = _records(selection.get("documents"), "documents")
    decision_entries = set(_ints(selection.get("decision_entry_numbers")))
    candidates = [
        document
        for document in documents
        if document.get("contains_target_outcome") is True
        or document.get("document_role") in {"decision", "order"}
    ]
    if not candidates:
        raise CycleLabelAuditError("selection has no decision document")
    candidates.sort(
        key=lambda document: (
            document.get("docket_entry_number") not in decision_entries,
            int(document.get("docket_entry_number") or 10**9),
        )
    )
    return _required_str(candidates[0], "source_document_id")


def _stratum(label: Mapping[str, Any]) -> str:
    resolution = UnitResolution(_required_str(label, "unit_resolution"))
    if resolution is UnitResolution.FULLY_DISMISSED:
        return "unanimous_grant"
    if resolution is UnitResolution.PARTIAL_DISMISSAL_ONLY:
        return "partial"
    if resolution is UnitResolution.SURVIVES_IN_MATERIAL_RESPECT:
        return "unanimous_deny"
    raise CycleLabelAuditError("ambiguous resolution cannot be auto-labeled")


def _label_signature(label: Mapping[str, Any]) -> tuple[object, ...]:
    return (
        _required_str(label, "unit_resolution"),
        label.get("fully_dismissed"),
        _required_str(label, "amendment_class"),
        label.get("ambiguous"),
        label.get("primary_outcome"),
        label.get("conditional_amendment_target"),
    )


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _mapping(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CycleLabelAuditError(f"{field} must be an object")
    return cast(Mapping[str, Any], value)


def _records(value: object, field: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise CycleLabelAuditError(f"{field} must be a list")
    records = tuple(cast(Sequence[object], value))
    if not all(isinstance(record, Mapping) for record in records):
        raise CycleLabelAuditError(f"{field} must contain objects")
    return cast(tuple[Mapping[str, Any], ...], records)


def _required_str(record: Mapping[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise CycleLabelAuditError(f"{field} is required")
    return value


def _required_int(record: Mapping[str, Any], field: str) -> int:
    value = record.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        raise CycleLabelAuditError(f"{field} must be an integer")
    return value


def _positive_int(record: Mapping[str, Any], field: str) -> int:
    value = _required_int(record, field)
    if value <= 0:
        raise CycleLabelAuditError(f"{field} must be positive")
    return value


def _probability(
    record: Mapping[str, Any], field: str, *, positive: bool = False
) -> float:
    value = record.get(field)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise CycleLabelAuditError(f"{field} must be numeric")
    result = float(value)
    if not 0 <= result <= 1 or (positive and result == 0):
        raise CycleLabelAuditError(
            f"{field} must be in {'(0, 1]' if positive else '[0, 1]'}"
        )
    return result


def _sha256(value: str, field: str) -> str:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise CycleLabelAuditError(f"{field} must be a lowercase SHA-256")
    return value


def _ints(value: object) -> tuple[int, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        return ()
    return tuple(
        item
        for item in cast(Sequence[object], value)
        if isinstance(item, int) and not isinstance(item, bool)
    )
