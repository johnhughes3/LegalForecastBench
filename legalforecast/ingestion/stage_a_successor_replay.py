"""Authenticated candidate-scoped Stage A successor replay.

The binder keeps the full predecessor cohort. It reuses settled unitizer and
reviewer outputs for unaffected candidates and routes unitizer/reviewer
callbacks only to candidates whose successor packet inputs changed. It never
subsets the lineage into a hand-authored five-case Stage A artifact.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import cast

from legalforecast.contracts import (
    ARTIFACT_RAW_SHA256_V1,
    STAGE_A_SUCCESSOR_REPLAY_V1,
    SUCCESSOR_RERUN_IMPACT_V1,
)
from legalforecast.ingestion.successor_rerun_impact import SuccessorRerunImpact
from legalforecast.labeling.llm_pipeline import (
    STAGE_A_CLAIM_ONTOLOGY_V4_PROMPT_CONTRACT,
    STAGE_A_CLAIM_ONTOLOGY_V5_PROMPT_CONTRACT,
)

SCHEMA_VERSION = str(STAGE_A_SUCCESSOR_REPLAY_V1)
UNITIZER_NAMESPACE = STAGE_A_CLAIM_ONTOLOGY_V5_PROMPT_CONTRACT
REVIEWER_NAMESPACE = STAGE_A_CLAIM_ONTOLOGY_V4_PROMPT_CONTRACT
_SHA256 = re.compile(r"[0-9a-f]{64}")
_REPLAY_AUTHORITY = object()
_RECEIPT_AUTHORITY = object()
_AUTHORITY = {
    "artifact": False,
    "dispatch": False,
    "execution": False,
    "freeze": False,
    "provider": False,
    "publication": False,
    "purchase": False,
}


class StageASuccessorReplayError(ValueError):
    """Raised when candidate-scoped Stage A replay is not authentic."""


@dataclass(frozen=True, slots=True)
class StageAStageOutcome:
    """One unitizer or reviewer result for a single affected candidate."""

    candidate_id: str
    record: Mapping[str, object]
    retry_count: int


@dataclass(frozen=True, slots=True, init=False)
class StageASuccessorReplay:
    """Exact reusable/execute partition bound to one full successor lineage."""

    cycle_id: str
    predecessor_candidate_ids: tuple[str, ...]
    successor_candidate_ids: tuple[str, ...]
    affected_candidate_ids: tuple[str, ...]
    reusable_candidate_ids: tuple[str, ...]
    unitizer_namespace: str
    reviewer_namespace: str
    predecessor_selection_sha256: str
    successor_selection_sha256: str
    successor_materialization_sha256: str
    successor_parser_sha256: str
    provider_journal_sha256: str
    impact_sha256: str
    provider_activity_requested: bool
    provider_activity_executed: bool
    replay_sha256: str
    _mint: object

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise StageASuccessorReplayError(
            "stage A successor replay can be created only by authenticated binding"
        )

    def is_replay_minted(self) -> bool:
        return self._mint is _REPLAY_AUTHORITY

    def content_record(self) -> dict[str, object]:
        return {
            "schema_version": SCHEMA_VERSION,
            "cycle_id": self.cycle_id,
            "predecessor_candidate_ids": list(self.predecessor_candidate_ids),
            "successor_candidate_ids": list(self.successor_candidate_ids),
            "affected_candidate_ids": list(self.affected_candidate_ids),
            "reusable_candidate_ids": list(self.reusable_candidate_ids),
            "unitizer_namespace": self.unitizer_namespace,
            "reviewer_namespace": self.reviewer_namespace,
            "predecessor_selection_sha256": self.predecessor_selection_sha256,
            "successor_selection_sha256": self.successor_selection_sha256,
            "successor_materialization_sha256": self.successor_materialization_sha256,
            "successor_parser_sha256": self.successor_parser_sha256,
            "provider_journal_sha256": self.provider_journal_sha256,
            "impact_sha256": self.impact_sha256,
            "provider_activity_requested": self.provider_activity_requested,
            "provider_activity_executed": self.provider_activity_executed,
            "authority": dict(_AUTHORITY),
        }

    def to_record(self) -> dict[str, object]:
        return {**self.content_record(), "replay_sha256": self.replay_sha256}


@dataclass(frozen=True, slots=True, init=False)
class StageASuccessorReplayReceipt:
    """Per-candidate timing and merged Stage A outputs for one bound replay."""

    replay_sha256: str
    unitizer_records: tuple[Mapping[str, object], ...]
    reviewer_records: tuple[Mapping[str, object], ...]
    candidates: tuple[Mapping[str, object], ...]
    provider_activity_requested: bool
    provider_activity_executed: bool
    receipt_sha256: str
    _mint: object

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise StageASuccessorReplayError(
            "stage A successor replay receipt can be created only by authenticated run"
        )

    def is_replay_minted(self) -> bool:
        return self._mint is _RECEIPT_AUTHORITY

    def content_record(self) -> dict[str, object]:
        return {
            "schema_version": SCHEMA_VERSION,
            "replay_sha256": self.replay_sha256,
            "unitizer_records": [dict(record) for record in self.unitizer_records],
            "reviewer_records": [dict(record) for record in self.reviewer_records],
            "candidates": [dict(row) for row in self.candidates],
            "provider_activity_requested": self.provider_activity_requested,
            "provider_activity_executed": self.provider_activity_executed,
            "authority": dict(_AUTHORITY),
        }

    def to_record(self) -> dict[str, object]:
        return {**self.content_record(), "receipt_sha256": self.receipt_sha256}


def bind_stage_a_successor_replay(
    *,
    impact: SuccessorRerunImpact,
    predecessor_candidate_ids: Sequence[str],
    successor_candidate_ids: Sequence[str],
    predecessor_selection_sha256: str,
    successor_selection_sha256: str,
    successor_materialization_sha256: str,
    successor_parser_sha256: str,
    provider_journal_sha256: str,
    unitizer_namespace: str,
    reviewer_namespace: str,
) -> StageASuccessorReplay:
    """Bind one successful advisory impact to the full successor cohort."""

    predecessor = _require_candidate_ids(
        predecessor_candidate_ids, "predecessor candidate IDs"
    )
    successor = _require_candidate_ids(
        successor_candidate_ids, "successor candidate IDs"
    )
    if successor != predecessor:
        raise StageASuccessorReplayError(
            "successor Stage A lineage must keep the exact predecessor cohort"
        )
    if not impact.ok:
        raise StageASuccessorReplayError("successor rerun impact is not successful")
    record = dict(impact.record)
    if record.get("schema_version") != str(SUCCESSOR_RERUN_IMPACT_V1):
        raise StageASuccessorReplayError("successor rerun impact schema is invalid")
    cycle_id = _required_str(record.get("cycle_id"), "cycle_id")
    commitments = _required_mapping(
        record.get("proposed_global_commitments"),
        "proposed_global_commitments",
    )
    if commitments.get("provider_attempt_namespace") != unitizer_namespace:
        raise StageASuccessorReplayError(
            "impact unitizer namespace differs from the bound v5 contract"
        )
    if unitizer_namespace != UNITIZER_NAMESPACE:
        raise StageASuccessorReplayError(
            "live Stage A successor replay requires claim-ontology-v5 unitizer"
        )
    if reviewer_namespace != REVIEWER_NAMESPACE:
        raise StageASuccessorReplayError(
            "live Stage A successor replay requires claim-ontology-v4 reviewer"
        )
    affected = _require_candidate_ids(
        _required_sequence(record.get("affected_candidates"), "affected_candidates"),
        "affected candidates",
    )
    reusable_calls = _required_sequence(
        record.get("reusable_logical_calls"), "reusable_logical_calls"
    )
    reusable: list[str] = []
    seen_reusable: set[str] = set()
    for raw_call in reusable_calls:
        call = _required_mapping(raw_call, "reusable logical call")
        candidate_id = _required_str(call.get("candidate_id"), "reusable candidate_id")
        if candidate_id in seen_reusable:
            raise StageASuccessorReplayError("reusable logical call is duplicated")
        _required_str(call.get("logical_call_key"), "logical_call_key")
        _require_positive_int(call.get("attempt_ordinal"), "attempt_ordinal")
        reusable.append(candidate_id)
        seen_reusable.add(candidate_id)
    reusable_ids = tuple(reusable)
    _require_partition(predecessor, affected=affected, reusable=reusable_ids)
    impact_sha256 = str(
        ARTIFACT_RAW_SHA256_V1.commit(record, domain=SUCCESSOR_RERUN_IMPACT_V1).digest
    )
    provisional = _mint_replay(
        cycle_id=cycle_id,
        predecessor_candidate_ids=predecessor,
        successor_candidate_ids=successor,
        affected_candidate_ids=affected,
        reusable_candidate_ids=reusable_ids,
        unitizer_namespace=unitizer_namespace,
        reviewer_namespace=reviewer_namespace,
        predecessor_selection_sha256=_digest(
            predecessor_selection_sha256, "predecessor selection digest"
        ),
        successor_selection_sha256=_digest(
            successor_selection_sha256, "successor selection digest"
        ),
        successor_materialization_sha256=_digest(
            successor_materialization_sha256, "successor materialization digest"
        ),
        successor_parser_sha256=_digest(
            successor_parser_sha256, "successor parser digest"
        ),
        provider_journal_sha256=_digest(
            provider_journal_sha256, "provider journal digest"
        ),
        impact_sha256=impact_sha256,
        provider_activity_requested=bool(affected),
        provider_activity_executed=False,
        replay_sha256="",
    )
    return _mint_replay(
        cycle_id=provisional.cycle_id,
        predecessor_candidate_ids=provisional.predecessor_candidate_ids,
        successor_candidate_ids=provisional.successor_candidate_ids,
        affected_candidate_ids=provisional.affected_candidate_ids,
        reusable_candidate_ids=provisional.reusable_candidate_ids,
        unitizer_namespace=provisional.unitizer_namespace,
        reviewer_namespace=provisional.reviewer_namespace,
        predecessor_selection_sha256=provisional.predecessor_selection_sha256,
        successor_selection_sha256=provisional.successor_selection_sha256,
        successor_materialization_sha256=provisional.successor_materialization_sha256,
        successor_parser_sha256=provisional.successor_parser_sha256,
        provider_journal_sha256=provisional.provider_journal_sha256,
        impact_sha256=provisional.impact_sha256,
        provider_activity_requested=provisional.provider_activity_requested,
        provider_activity_executed=False,
        replay_sha256=_commit_replay(provisional.content_record()),
    )


def run_stage_a_successor_replay(
    *,
    replay: StageASuccessorReplay,
    prior_unitizer_records: Mapping[str, Mapping[str, object]],
    prior_reviewer_records: Mapping[str, Mapping[str, object]],
    unitize: Callable[[str], StageAStageOutcome],
    review: Callable[[str], StageAStageOutcome],
    monotonic: Callable[[], float],
) -> StageASuccessorReplayReceipt:
    """Reuse unaffected Stage A outputs and execute only affected candidates."""

    _require_replay_minted(replay)
    unitizer_records: list[Mapping[str, object]] = []
    reviewer_records: list[Mapping[str, object]] = []
    candidate_rows: list[Mapping[str, object]] = []
    reusable = set(replay.reusable_candidate_ids)
    executed = False
    for candidate_id in replay.predecessor_candidate_ids:
        if candidate_id in reusable:
            unitizer_records.append(
                _prior_record(
                    prior_unitizer_records,
                    candidate_id=candidate_id,
                    label="unitizer",
                )
            )
            reviewer_records.append(
                _prior_record(
                    prior_reviewer_records,
                    candidate_id=candidate_id,
                    label="reviewer",
                )
            )
            candidate_rows.append(
                _candidate_row(
                    candidate_id=candidate_id,
                    disposition="reused",
                    unitizer_duration_seconds="0",
                    reviewer_duration_seconds="0",
                    retry_count=0,
                )
            )
            continue
        unitizer_started = monotonic()
        unitizer_outcome = unitize(candidate_id)
        unitizer_finished = monotonic()
        _require_outcome(unitizer_outcome, candidate_id=candidate_id, stage="unitizer")
        reviewer_started = monotonic()
        reviewer_outcome = review(candidate_id)
        reviewer_finished = monotonic()
        _require_outcome(reviewer_outcome, candidate_id=candidate_id, stage="reviewer")
        executed = True
        unitizer_records.append(dict(unitizer_outcome.record))
        reviewer_records.append(dict(reviewer_outcome.record))
        candidate_rows.append(
            _candidate_row(
                candidate_id=candidate_id,
                disposition="executed",
                unitizer_duration_seconds=_duration(
                    unitizer_started, unitizer_finished, "unitizer duration"
                ),
                reviewer_duration_seconds=_duration(
                    reviewer_started, reviewer_finished, "reviewer duration"
                ),
                retry_count=unitizer_outcome.retry_count + reviewer_outcome.retry_count,
            )
        )
    if {row["candidate_id"] for row in candidate_rows} != set(
        replay.predecessor_candidate_ids
    ):
        raise StageASuccessorReplayError("merged Stage A output dropped a candidate")
    provisional = _mint_receipt(
        replay_sha256=replay.replay_sha256,
        unitizer_records=tuple(unitizer_records),
        reviewer_records=tuple(reviewer_records),
        candidates=tuple(candidate_rows),
        provider_activity_requested=replay.provider_activity_requested,
        provider_activity_executed=executed,
        receipt_sha256="",
    )
    return _mint_receipt(
        replay_sha256=provisional.replay_sha256,
        unitizer_records=provisional.unitizer_records,
        reviewer_records=provisional.reviewer_records,
        candidates=provisional.candidates,
        provider_activity_requested=provisional.provider_activity_requested,
        provider_activity_executed=provisional.provider_activity_executed,
        receipt_sha256=_commit_receipt(provisional.content_record()),
    )


def _require_partition(
    cohort: tuple[str, ...],
    *,
    affected: tuple[str, ...],
    reusable: tuple[str, ...],
) -> None:
    cohort_set = set(cohort)
    affected_set = set(affected)
    reusable_set = set(reusable)
    if affected_set & reusable_set:
        raise StageASuccessorReplayError(
            "affected and reusable Stage A candidates overlap"
        )
    if affected_set - cohort_set:
        raise StageASuccessorReplayError(
            "affected candidate is outside the predecessor cohort"
        )
    if reusable_set - cohort_set:
        raise StageASuccessorReplayError(
            "reusable candidate is outside the predecessor cohort"
        )
    if affected_set | reusable_set != cohort_set:
        raise StageASuccessorReplayError(
            "reusable and affected candidates must cover the full successor cohort"
        )


def _prior_record(
    records: Mapping[str, Mapping[str, object]],
    *,
    candidate_id: str,
    label: str,
) -> dict[str, object]:
    try:
        record = records[candidate_id]
    except KeyError as exc:
        raise StageASuccessorReplayError(
            f"reusable {label} record is missing: {candidate_id}"
        ) from exc
    copied = dict(record)
    if copied.get("candidate_id") != candidate_id:
        raise StageASuccessorReplayError(
            f"reusable {label} record candidate ID differs: {candidate_id}"
        )
    return copied


def _require_outcome(
    outcome: StageAStageOutcome, *, candidate_id: str, stage: str
) -> None:
    if type(outcome) is not StageAStageOutcome:
        raise StageASuccessorReplayError(f"{stage} outcome is not authenticated")
    if outcome.candidate_id != candidate_id:
        raise StageASuccessorReplayError(f"{stage} outcome candidate ID differs")
    if outcome.retry_count < 0:
        raise StageASuccessorReplayError(f"{stage} retry count is invalid")
    if outcome.record.get("candidate_id") != candidate_id:
        raise StageASuccessorReplayError(f"{stage} record candidate ID differs")


def _candidate_row(
    *,
    candidate_id: str,
    disposition: str,
    unitizer_duration_seconds: str,
    reviewer_duration_seconds: str,
    retry_count: int,
) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "disposition": disposition,
        "unitizer_duration_seconds": unitizer_duration_seconds,
        "reviewer_duration_seconds": reviewer_duration_seconds,
        "retry_count": retry_count,
    }


def _require_candidate_ids(values: object, label: str) -> tuple[str, ...]:
    ids: list[str] = []
    seen: set[str] = set()
    for raw in _required_sequence(values, label):
        candidate_id = _required_str(raw, label)
        if candidate_id in seen:
            raise StageASuccessorReplayError(f"{label} contain a duplicate")
        ids.append(candidate_id)
        seen.add(candidate_id)
    if not ids:
        raise StageASuccessorReplayError(f"{label} are empty")
    return tuple(ids)
    ids: list[str] = []
    seen: set[str] = set()
    for raw in values:
        candidate_id = _required_str(raw, label)
        if candidate_id in seen:
            raise StageASuccessorReplayError(f"{label} contain a duplicate")
        ids.append(candidate_id)
        seen.add(candidate_id)
    if not ids:
        raise StageASuccessorReplayError(f"{label} are empty")
    return tuple(ids)


def _required_sequence(value: object, label: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise StageASuccessorReplayError(f"{label} is invalid")
    return cast(Sequence[object], value)


def _required_mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise StageASuccessorReplayError(f"{label} is invalid")
    return cast(Mapping[str, object], value)


def _required_str(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise StageASuccessorReplayError(f"{label} is invalid")
    return value


def _require_positive_int(value: object, label: str) -> int:
    if type(value) is not int or value < 1:
        raise StageASuccessorReplayError(f"{label} is invalid")
    return value


def _digest(value: str, label: str) -> str:
    digest = value.removeprefix("sha256:")
    if _SHA256.fullmatch(digest) is None:
        raise StageASuccessorReplayError(f"{label} is invalid")
    return digest


def _duration(started: float, finished: float, label: str) -> str:
    duration = Decimal(str(finished)) - Decimal(str(started))
    if duration < 0:
        raise StageASuccessorReplayError(f"{label} moved backwards")
    return str(duration)


def _require_replay_minted(replay: StageASuccessorReplay) -> None:
    if type(replay) is not StageASuccessorReplay or not replay.is_replay_minted():
        raise StageASuccessorReplayError("replay lacks authenticated binding")
    if _commit_replay(replay.content_record()) != replay.replay_sha256:
        raise StageASuccessorReplayError("replay changed after binding")


def _commit_replay(record: Mapping[str, object]) -> str:
    return str(
        ARTIFACT_RAW_SHA256_V1.commit(record, domain=STAGE_A_SUCCESSOR_REPLAY_V1).digest
    )


def _commit_receipt(record: Mapping[str, object]) -> str:
    return str(
        ARTIFACT_RAW_SHA256_V1.commit(record, domain=STAGE_A_SUCCESSOR_REPLAY_V1).digest
    )


def _mint_replay(**fields: object) -> StageASuccessorReplay:
    replay = object.__new__(StageASuccessorReplay)
    for name, value in (*fields.items(), ("_mint", _REPLAY_AUTHORITY)):
        object.__setattr__(replay, name, value)
    return replay


def _mint_receipt(**fields: object) -> StageASuccessorReplayReceipt:
    receipt = object.__new__(StageASuccessorReplayReceipt)
    for name, value in (*fields.items(), ("_mint", _RECEIPT_AUTHORITY)):
        object.__setattr__(receipt, name, value)
    return receipt
