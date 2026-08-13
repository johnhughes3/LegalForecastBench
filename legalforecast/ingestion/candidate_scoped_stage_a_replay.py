"""Authenticated candidate-scoped Stage A successor replay.

This module classifies each successor packet against the predecessor Stage A
lineage, reuses byte-identical prior unitizer/reviewer results when packet
inputs are unchanged, and invokes injected unitizer/reviewer callbacks only
for candidates whose packet identity changed. It never opens a provider
journal, never constructs a transport, and never subsets the predecessor
candidate set: the sealed successor Stage A lineage covers every predecessor
candidate in predecessor order.

The live Cycle 1 pair is ``claim-ontology-v5`` unitizer plus
``claim-ontology-v4`` reviewer, bound to the shared provider caps digest and
journal path. Terminal predecessor statuses are not retried when inputs
match. Unknown rerun outcomes are permanently nonretryable and cannot seal.
"""

from __future__ import annotations

import os
import re
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from legalforecast.contracts import (
    ARTIFACT_RAW_SHA256_V1,
    CANDIDATE_SCOPED_STAGE_A_REPLAY_RECEIPT_V1,
    CANDIDATE_SCOPED_STAGE_A_REPLAY_V1,
    SchemaIdentifier,
)

PLAN_SCHEMA_VERSION = str(CANDIDATE_SCOPED_STAGE_A_REPLAY_V1)
RECEIPT_SCHEMA_VERSION = str(CANDIDATE_SCOPED_STAGE_A_REPLAY_RECEIPT_V1)
UNITIZER_NAMESPACE = "claim-ontology-v5"
REVIEWER_NAMESPACE = "claim-ontology-v4"

Disposition = Literal["reused", "rerun"]
StageStatus = Literal[
    "settled",
    "reconstruction_failed",
    "terminal_escalation",
    "unknown",
]

_SHA256 = re.compile(r"[0-9a-f]{64}")
_TERMINAL_STATUSES = frozenset(
    {"settled", "reconstruction_failed", "terminal_escalation"}
)
_OUTCOME_STATUSES = _TERMINAL_STATUSES | {"unknown"}
_PLAN_AUTHORITY = object()
_EXECUTION_AUTHORITY = object()
_RECEIPT_AUTHORITY = object()


class CandidateScopedStageAReplayError(ValueError):
    """Raised when candidate-scoped Stage A replay is not authentic."""


@dataclass(frozen=True, slots=True)
class PacketDocument:
    """Exact source-byte identity for one packet document."""

    source_document_id: str
    document_role: str
    sha256: str
    byte_count: int


@dataclass(frozen=True, slots=True)
class ParserOutputIdentity:
    """Authenticated parser-output identity for one packet document."""

    source_document_id: str
    markdown_sha256: str
    parser_reuse_identity_sha256: str


@dataclass(frozen=True, slots=True)
class CandidatePacketInput:
    """Successor or predecessor packet inputs for one candidate."""

    candidate_id: str
    case_id: str
    selection_record: Mapping[str, object]
    documents: tuple[PacketDocument, ...]
    parser_outputs: tuple[ParserOutputIdentity, ...]


@dataclass(frozen=True, slots=True)
class PredecessorCandidateStageA:
    """Authenticated prior Stage A results for one candidate."""

    packet: CandidatePacketInput
    unitize_record: Mapping[str, object]
    unitize_audit: Mapping[str, object]
    review_flags: tuple[Mapping[str, object], ...]
    review_audit: Mapping[str, object]
    unitizer_status: StageStatus
    reviewer_status: StageStatus


@dataclass(frozen=True, slots=True)
class PredecessorStageALineage:
    """Complete predecessor Stage A lineage bound to shared provider identity."""

    candidates: tuple[PredecessorCandidateStageA, ...]
    unitizer_namespace: str
    reviewer_namespace: str
    provider_caps_sha256: str
    provider_journal_path: Path
    selection_sha256: str
    materialization_sha256: str
    parser_sha256: str


@dataclass(frozen=True, slots=True)
class CandidateReplayDecision:
    """Reuse-versus-rerun classification for one candidate."""

    candidate_id: str
    case_id: str
    disposition: Disposition
    predecessor_packet_sha256: str
    successor_packet_sha256: str
    unitizer_status: StageStatus
    reviewer_status: StageStatus


@dataclass(frozen=True, slots=True)
class StageAStageOutcome:
    """Injected unitizer or reviewer result for one rerun candidate."""

    candidate_id: str
    records: tuple[Mapping[str, object], ...]
    audit: Mapping[str, object]
    status: StageStatus


@dataclass(frozen=True, slots=True)
class CandidateStageATiming:
    """Monotonic timing for one candidate's reuse or rerun."""

    candidate_id: str
    disposition: Disposition
    elapsed_ms: int
    unitizer_elapsed_ms: int
    reviewer_elapsed_ms: int


@dataclass(frozen=True, slots=True, init=False)
class CandidateScopedStageAPlan:
    """Replay-minted classification of reuse versus rerun candidates."""

    predecessor_selection_sha256: str
    predecessor_materialization_sha256: str
    predecessor_parser_sha256: str
    successor_selection_sha256: str
    successor_materialization_sha256: str
    successor_parser_sha256: str
    unitizer_namespace: str
    reviewer_namespace: str
    provider_caps_sha256: str
    provider_journal_path: Path
    candidate_ids: tuple[str, ...]
    decisions: tuple[CandidateReplayDecision, ...]
    reused_candidate_ids: tuple[str, ...]
    rerun_candidate_ids: tuple[str, ...]
    plan_sha256: str
    predecessor_candidates: tuple[PredecessorCandidateStageA, ...]
    successor_packets: tuple[CandidatePacketInput, ...]
    _mint: object

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise CandidateScopedStageAReplayError(
            "candidate-scoped Stage A plan can be created only by authenticated replay"
        )

    def is_replay_minted(self) -> bool:
        return self._mint is _PLAN_AUTHORITY

    def to_record(self) -> dict[str, object]:
        return {**self.content_record(), "plan_sha256": self.plan_sha256}

    def content_record(self) -> dict[str, object]:
        return {
            "schema_version": PLAN_SCHEMA_VERSION,
            "predecessor_selection_sha256": self.predecessor_selection_sha256,
            "predecessor_materialization_sha256": (
                self.predecessor_materialization_sha256
            ),
            "predecessor_parser_sha256": self.predecessor_parser_sha256,
            "successor_selection_sha256": self.successor_selection_sha256,
            "successor_materialization_sha256": self.successor_materialization_sha256,
            "successor_parser_sha256": self.successor_parser_sha256,
            "unitizer_namespace": self.unitizer_namespace,
            "reviewer_namespace": self.reviewer_namespace,
            "provider_caps_sha256": self.provider_caps_sha256,
            "provider_journal_path": os.path.abspath(self.provider_journal_path),
            "candidate_ids": list(self.candidate_ids),
            "decisions": [
                {
                    "candidate_id": decision.candidate_id,
                    "case_id": decision.case_id,
                    "disposition": decision.disposition,
                    "predecessor_packet_sha256": decision.predecessor_packet_sha256,
                    "successor_packet_sha256": decision.successor_packet_sha256,
                    "unitizer_status": decision.unitizer_status,
                    "reviewer_status": decision.reviewer_status,
                }
                for decision in self.decisions
            ],
            "reused_candidate_ids": list(self.reused_candidate_ids),
            "rerun_candidate_ids": list(self.rerun_candidate_ids),
        }


@dataclass(frozen=True, slots=True, init=False)
class CandidateScopedStageAExecution:
    """One-shot execution of the minted plan against injected stage callbacks."""

    plan_sha256: str
    reused_candidate_ids: tuple[str, ...]
    rerun_candidate_ids: tuple[str, ...]
    unitize_records: tuple[Mapping[str, object], ...]
    unitize_audits: tuple[Mapping[str, object], ...]
    review_flags: tuple[Mapping[str, object], ...]
    review_audits: tuple[Mapping[str, object], ...]
    timings: tuple[CandidateStageATiming, ...]
    statuses: tuple[tuple[str, StageStatus, StageStatus], ...]
    provider_journal_path: Path
    _mint: object

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise CandidateScopedStageAReplayError(
            "candidate-scoped Stage A execution can be created only by "
            "authenticated replay"
        )

    def is_replay_minted(self) -> bool:
        return self._mint is _EXECUTION_AUTHORITY


@dataclass(frozen=True, slots=True, init=False)
class CandidateScopedStageAReceipt:
    """Sealed complete successor Stage A lineage for every predecessor candidate."""

    schema_version: str
    plan_sha256: str
    successor_selection_sha256: str
    successor_materialization_sha256: str
    successor_parser_sha256: str
    unitizer_namespace: str
    reviewer_namespace: str
    provider_caps_sha256: str
    provider_journal_path: Path
    candidate_ids: tuple[str, ...]
    reused_candidate_ids: tuple[str, ...]
    rerun_candidate_ids: tuple[str, ...]
    unitize_records: tuple[Mapping[str, object], ...]
    unitize_audits: tuple[Mapping[str, object], ...]
    review_flags: tuple[Mapping[str, object], ...]
    review_audits: tuple[Mapping[str, object], ...]
    timings: tuple[CandidateStageATiming, ...]
    receipt_sha256: str
    _mint: object

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise CandidateScopedStageAReplayError(
            "candidate-scoped Stage A receipt can be created only by authenticated "
            "replay"
        )

    def is_replay_minted(self) -> bool:
        return self._mint is _RECEIPT_AUTHORITY

    def to_record(self) -> dict[str, object]:
        return {**self.content_record(), "receipt_sha256": self.receipt_sha256}

    def content_record(self) -> dict[str, object]:
        return {
            "schema_version": RECEIPT_SCHEMA_VERSION,
            "plan_sha256": self.plan_sha256,
            "successor_selection_sha256": self.successor_selection_sha256,
            "successor_materialization_sha256": self.successor_materialization_sha256,
            "successor_parser_sha256": self.successor_parser_sha256,
            "unitizer_namespace": self.unitizer_namespace,
            "reviewer_namespace": self.reviewer_namespace,
            "provider_caps_sha256": self.provider_caps_sha256,
            "provider_journal_path": os.path.abspath(self.provider_journal_path),
            "candidate_ids": list(self.candidate_ids),
            "reused_candidate_ids": list(self.reused_candidate_ids),
            "rerun_candidate_ids": list(self.rerun_candidate_ids),
            "unitize_records": [dict(record) for record in self.unitize_records],
            "unitize_audits": [dict(record) for record in self.unitize_audits],
            "review_flags": [dict(record) for record in self.review_flags],
            "review_audits": [dict(record) for record in self.review_audits],
            "timings": [
                {
                    "candidate_id": timing.candidate_id,
                    "disposition": timing.disposition,
                    "elapsed_ms": timing.elapsed_ms,
                    "unitizer_elapsed_ms": timing.unitizer_elapsed_ms,
                    "reviewer_elapsed_ms": timing.reviewer_elapsed_ms,
                }
                for timing in self.timings
            ],
        }


UnitizerCallback = Callable[[str], StageAStageOutcome]
ReviewerCallback = Callable[[str, StageAStageOutcome], StageAStageOutcome]
Clock = Callable[[], float]


def packet_input_identity_sha256(packet: CandidatePacketInput) -> str:
    """Commit one candidate's selection, document, and parser identities."""

    _require_candidate_id(packet.candidate_id)
    _require_nonempty(packet.case_id, "case_id")
    documents = tuple(
        sorted(packet.documents, key=lambda document: document.source_document_id)
    )
    parser_outputs = tuple(
        sorted(
            packet.parser_outputs,
            key=lambda output: output.source_document_id,
        )
    )
    document_ids = [document.source_document_id for document in documents]
    parser_ids = [output.source_document_id for output in parser_outputs]
    if len(set(document_ids)) != len(document_ids):
        raise CandidateScopedStageAReplayError(
            "packet documents repeat a source_document_id"
        )
    if len(set(parser_ids)) != len(parser_ids):
        raise CandidateScopedStageAReplayError(
            "parser outputs repeat a source_document_id"
        )
    if set(document_ids) != set(parser_ids):
        raise CandidateScopedStageAReplayError(
            "parser outputs must cover every packet document"
        )
    payload = {
        "candidate_id": packet.candidate_id,
        "case_id": packet.case_id,
        "selection": dict(packet.selection_record),
        "documents": [
            {
                "source_document_id": document.source_document_id,
                "document_role": document.document_role,
                "sha256": _digest(document.sha256, "document digest"),
                "byte_count": _byte_count(document.byte_count),
            }
            for document in documents
        ],
        "parser_outputs": [
            {
                "source_document_id": output.source_document_id,
                "markdown_sha256": _digest(output.markdown_sha256, "markdown digest"),
                "parser_reuse_identity_sha256": _digest(
                    output.parser_reuse_identity_sha256,
                    "parser reuse identity",
                ),
            }
            for output in parser_outputs
        ],
    }
    return _commit(payload, CANDIDATE_SCOPED_STAGE_A_REPLAY_V1)


def plan_candidate_scoped_stage_a_replay(
    *,
    predecessor: PredecessorStageALineage,
    successor_packets: Sequence[CandidatePacketInput],
    successor_selection_sha256: str,
    successor_materialization_sha256: str,
    successor_parser_sha256: str,
    unitizer_namespace: str,
    reviewer_namespace: str,
    provider_caps_sha256: str,
    provider_journal_path: Path,
) -> CandidateScopedStageAPlan:
    """Classify reuse versus rerun without opening provider or execution authority."""

    _require_live_namespace_pair(
        unitizer_namespace=unitizer_namespace,
        reviewer_namespace=reviewer_namespace,
    )
    if (
        predecessor.unitizer_namespace != unitizer_namespace
        or predecessor.reviewer_namespace != reviewer_namespace
    ):
        raise CandidateScopedStageAReplayError(
            "predecessor Stage A namespace pair differs from the live v5/v4 successor"
        )
    _require_digest(predecessor.provider_caps_sha256, "predecessor provider caps")
    caps_digest = _digest(provider_caps_sha256, "provider caps digest")
    if caps_digest != predecessor.provider_caps_sha256:
        raise CandidateScopedStageAReplayError(
            "successor provider caps digest differs from the shared predecessor caps"
        )
    journal_path = Path(os.path.abspath(provider_journal_path))
    predecessor_journal = Path(os.path.abspath(predecessor.provider_journal_path))
    if journal_path != predecessor_journal:
        raise CandidateScopedStageAReplayError(
            "successor provider journal is not the shared predecessor journal"
        )
    predecessor_candidates = _require_predecessor_candidates(predecessor.candidates)
    successor = _require_successor_packets(
        successor_packets, predecessor_candidates=predecessor_candidates
    )
    decisions: list[CandidateReplayDecision] = []
    reused: list[str] = []
    rerun: list[str] = []
    for prior in predecessor_candidates:
        packet = successor[prior.packet.candidate_id]
        if packet.case_id != prior.packet.case_id:
            raise CandidateScopedStageAReplayError(
                f"successor case_id differs for {prior.packet.candidate_id}"
            )
        predecessor_packet_sha256 = packet_input_identity_sha256(prior.packet)
        successor_packet_sha256 = packet_input_identity_sha256(packet)
        if predecessor_packet_sha256 == successor_packet_sha256:
            disposition: Disposition = "reused"
            reused.append(prior.packet.candidate_id)
            unitizer_status = prior.unitizer_status
            reviewer_status = prior.reviewer_status
        else:
            disposition = "rerun"
            rerun.append(prior.packet.candidate_id)
            unitizer_status = "settled"
            reviewer_status = "settled"
        decisions.append(
            CandidateReplayDecision(
                candidate_id=prior.packet.candidate_id,
                case_id=prior.packet.case_id,
                disposition=disposition,
                predecessor_packet_sha256=predecessor_packet_sha256,
                successor_packet_sha256=successor_packet_sha256,
                unitizer_status=unitizer_status,
                reviewer_status=reviewer_status,
            )
        )
    candidate_ids = tuple(prior.packet.candidate_id for prior in predecessor_candidates)
    provisional = _mint_plan(
        predecessor_selection_sha256=_digest(
            predecessor.selection_sha256, "predecessor selection digest"
        ),
        predecessor_materialization_sha256=_digest(
            predecessor.materialization_sha256,
            "predecessor materialization digest",
        ),
        predecessor_parser_sha256=_digest(
            predecessor.parser_sha256, "predecessor parser digest"
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
        unitizer_namespace=unitizer_namespace,
        reviewer_namespace=reviewer_namespace,
        provider_caps_sha256=caps_digest,
        provider_journal_path=journal_path,
        candidate_ids=candidate_ids,
        decisions=tuple(decisions),
        reused_candidate_ids=tuple(reused),
        rerun_candidate_ids=tuple(rerun),
        plan_sha256="",
        predecessor_candidates=predecessor_candidates,
        successor_packets=tuple(
            successor[candidate_id] for candidate_id in candidate_ids
        ),
    )
    return _mint_plan(
        predecessor_selection_sha256=provisional.predecessor_selection_sha256,
        predecessor_materialization_sha256=(
            provisional.predecessor_materialization_sha256
        ),
        predecessor_parser_sha256=provisional.predecessor_parser_sha256,
        successor_selection_sha256=provisional.successor_selection_sha256,
        successor_materialization_sha256=provisional.successor_materialization_sha256,
        successor_parser_sha256=provisional.successor_parser_sha256,
        unitizer_namespace=provisional.unitizer_namespace,
        reviewer_namespace=provisional.reviewer_namespace,
        provider_caps_sha256=provisional.provider_caps_sha256,
        provider_journal_path=provisional.provider_journal_path,
        candidate_ids=provisional.candidate_ids,
        decisions=provisional.decisions,
        reused_candidate_ids=provisional.reused_candidate_ids,
        rerun_candidate_ids=provisional.rerun_candidate_ids,
        plan_sha256=_commit(
            provisional.content_record(),
            CANDIDATE_SCOPED_STAGE_A_REPLAY_V1,
        ),
        predecessor_candidates=provisional.predecessor_candidates,
        successor_packets=provisional.successor_packets,
    )


def run_candidate_scoped_stage_a_replay(
    plan: CandidateScopedStageAPlan,
    *,
    unitizer: UnitizerCallback,
    reviewer: ReviewerCallback,
    clock: Clock | None = None,
) -> CandidateScopedStageAExecution:
    """Execute unitizer/reviewer only for rerun candidates; reuse the rest."""

    _require_replay_minted_plan(plan)
    if tuple(packet.candidate_id for packet in plan.successor_packets) != (
        plan.candidate_ids
    ):
        raise CandidateScopedStageAReplayError(
            "successor packets drifted from the minted candidate order"
        )
    tick = clock or time.monotonic
    predecessor_by_id = {
        prior.packet.candidate_id: prior for prior in plan.predecessor_candidates
    }
    unitize_records: list[Mapping[str, object]] = []
    unitize_audits: list[Mapping[str, object]] = []
    review_flags: list[Mapping[str, object]] = []
    review_audits: list[Mapping[str, object]] = []
    timings: list[CandidateStageATiming] = []
    statuses: list[tuple[str, StageStatus, StageStatus]] = []
    attempted: set[str] = set()
    for decision in plan.decisions:
        prior = predecessor_by_id[decision.candidate_id]
        if decision.disposition == "reused":
            unitize_records.append(dict(prior.unitize_record))
            unitize_audits.append(dict(prior.unitize_audit))
            review_flags.extend(dict(flag) for flag in prior.review_flags)
            review_audits.append(dict(prior.review_audit))
            timings.append(
                CandidateStageATiming(
                    candidate_id=decision.candidate_id,
                    disposition="reused",
                    elapsed_ms=0,
                    unitizer_elapsed_ms=0,
                    reviewer_elapsed_ms=0,
                )
            )
            statuses.append(
                (decision.candidate_id, prior.unitizer_status, prior.reviewer_status)
            )
            continue
        if decision.candidate_id in attempted:
            raise CandidateScopedStageAReplayError(
                f"rerun candidate was retried: {decision.candidate_id}"
            )
        attempted.add(decision.candidate_id)
        started = tick()
        unitize_outcome = unitizer(decision.candidate_id)
        after_unitizer = tick()
        _require_outcome(unitize_outcome, decision.candidate_id, stage="unitizer")
        if unitize_outcome.status == "unknown":
            unitize_records.append(_single_record(unitize_outcome, "unitizer"))
            unitize_audits.append(dict(unitize_outcome.audit))
            timings.append(
                CandidateStageATiming(
                    candidate_id=decision.candidate_id,
                    disposition="rerun",
                    elapsed_ms=_elapsed_ms(started, after_unitizer),
                    unitizer_elapsed_ms=_elapsed_ms(started, after_unitizer),
                    reviewer_elapsed_ms=0,
                )
            )
            statuses.append((decision.candidate_id, "unknown", "unknown"))
            continue
        if unitize_outcome.status in {"reconstruction_failed", "terminal_escalation"}:
            unitize_records.append(_single_record(unitize_outcome, "unitizer"))
            unitize_audits.append(dict(unitize_outcome.audit))
            review_audits.append(
                {
                    "candidate_id": decision.candidate_id,
                    "status": "not_attempted_after_unitizer_terminal",
                }
            )
            timings.append(
                CandidateStageATiming(
                    candidate_id=decision.candidate_id,
                    disposition="rerun",
                    elapsed_ms=_elapsed_ms(started, after_unitizer),
                    unitizer_elapsed_ms=_elapsed_ms(started, after_unitizer),
                    reviewer_elapsed_ms=0,
                )
            )
            statuses.append(
                (decision.candidate_id, unitize_outcome.status, unitize_outcome.status)
            )
            continue
        review_outcome = reviewer(decision.candidate_id, unitize_outcome)
        finished = tick()
        _require_outcome(review_outcome, decision.candidate_id, stage="reviewer")
        unitize_records.append(_single_record(unitize_outcome, "unitizer"))
        unitize_audits.append(dict(unitize_outcome.audit))
        review_flags.extend(dict(record) for record in review_outcome.records)
        review_audits.append(dict(review_outcome.audit))
        timings.append(
            CandidateStageATiming(
                candidate_id=decision.candidate_id,
                disposition="rerun",
                elapsed_ms=_elapsed_ms(started, finished),
                unitizer_elapsed_ms=_elapsed_ms(started, after_unitizer),
                reviewer_elapsed_ms=_elapsed_ms(after_unitizer, finished),
            )
        )
        statuses.append(
            (decision.candidate_id, unitize_outcome.status, review_outcome.status)
        )
    return _mint_execution(
        plan_sha256=plan.plan_sha256,
        reused_candidate_ids=plan.reused_candidate_ids,
        rerun_candidate_ids=plan.rerun_candidate_ids,
        unitize_records=tuple(unitize_records),
        unitize_audits=tuple(unitize_audits),
        review_flags=tuple(review_flags),
        review_audits=tuple(review_audits),
        timings=tuple(timings),
        statuses=tuple(statuses),
        provider_journal_path=plan.provider_journal_path,
    )


def seal_candidate_scoped_stage_a_replay(
    plan: CandidateScopedStageAPlan,
    execution: CandidateScopedStageAExecution,
) -> CandidateScopedStageAReceipt:
    """Seal a complete successor Stage A lineage from one authenticated execution."""

    _require_replay_minted_plan(plan)
    _require_replay_minted_execution(execution)
    if execution.plan_sha256 != plan.plan_sha256:
        raise CandidateScopedStageAReplayError(
            "execution plan digest differs from the minted plan"
        )
    if execution.reused_candidate_ids != plan.reused_candidate_ids:
        raise CandidateScopedStageAReplayError("execution reuse set drifted from plan")
    if execution.rerun_candidate_ids != plan.rerun_candidate_ids:
        raise CandidateScopedStageAReplayError("execution rerun set drifted from plan")
    if tuple(record[0] for record in execution.statuses) != plan.candidate_ids:
        raise CandidateScopedStageAReplayError(
            "execution does not cover the predecessor candidate order"
        )
    if len(execution.unitize_records) != len(plan.candidate_ids):
        raise CandidateScopedStageAReplayError(
            "sealed Stage A lineage would subset the predecessor candidates"
        )
    for candidate_id, unitizer_status, reviewer_status in execution.statuses:
        if (
            unitizer_status not in _TERMINAL_STATUSES
            or reviewer_status not in _TERMINAL_STATUSES
        ):
            raise CandidateScopedStageAReplayError(
                f"unknown Stage A outcome cannot seal: {candidate_id}"
            )
    provisional = _mint_receipt(
        schema_version=RECEIPT_SCHEMA_VERSION,
        plan_sha256=plan.plan_sha256,
        successor_selection_sha256=plan.successor_selection_sha256,
        successor_materialization_sha256=plan.successor_materialization_sha256,
        successor_parser_sha256=plan.successor_parser_sha256,
        unitizer_namespace=plan.unitizer_namespace,
        reviewer_namespace=plan.reviewer_namespace,
        provider_caps_sha256=plan.provider_caps_sha256,
        provider_journal_path=plan.provider_journal_path,
        candidate_ids=plan.candidate_ids,
        reused_candidate_ids=plan.reused_candidate_ids,
        rerun_candidate_ids=plan.rerun_candidate_ids,
        unitize_records=execution.unitize_records,
        unitize_audits=execution.unitize_audits,
        review_flags=execution.review_flags,
        review_audits=execution.review_audits,
        timings=execution.timings,
        receipt_sha256="",
    )
    return _mint_receipt(
        schema_version=provisional.schema_version,
        plan_sha256=provisional.plan_sha256,
        successor_selection_sha256=provisional.successor_selection_sha256,
        successor_materialization_sha256=provisional.successor_materialization_sha256,
        successor_parser_sha256=provisional.successor_parser_sha256,
        unitizer_namespace=provisional.unitizer_namespace,
        reviewer_namespace=provisional.reviewer_namespace,
        provider_caps_sha256=provisional.provider_caps_sha256,
        provider_journal_path=provisional.provider_journal_path,
        candidate_ids=provisional.candidate_ids,
        reused_candidate_ids=provisional.reused_candidate_ids,
        rerun_candidate_ids=provisional.rerun_candidate_ids,
        unitize_records=provisional.unitize_records,
        unitize_audits=provisional.unitize_audits,
        review_flags=provisional.review_flags,
        review_audits=provisional.review_audits,
        timings=provisional.timings,
        receipt_sha256=_commit(
            provisional.content_record(),
            CANDIDATE_SCOPED_STAGE_A_REPLAY_RECEIPT_V1,
        ),
    )


def _require_live_namespace_pair(
    *, unitizer_namespace: str, reviewer_namespace: str
) -> None:
    if (unitizer_namespace, reviewer_namespace) != (
        UNITIZER_NAMESPACE,
        REVIEWER_NAMESPACE,
    ):
        raise CandidateScopedStageAReplayError(
            "candidate-scoped Stage A replay requires "
            f"{UNITIZER_NAMESPACE}/{REVIEWER_NAMESPACE} namespaces"
        )


def _require_predecessor_candidates(
    candidates: Sequence[PredecessorCandidateStageA],
) -> tuple[PredecessorCandidateStageA, ...]:
    if not candidates:
        raise CandidateScopedStageAReplayError("predecessor Stage A lineage is empty")
    seen: set[str] = set()
    ordered: list[PredecessorCandidateStageA] = []
    for prior in candidates:
        candidate_id = prior.packet.candidate_id
        _require_candidate_id(candidate_id)
        if candidate_id in seen:
            raise CandidateScopedStageAReplayError(
                f"predecessor Stage A lineage repeats {candidate_id}"
            )
        seen.add(candidate_id)
        _require_status(prior.unitizer_status, "predecessor unitizer status")
        _require_status(prior.reviewer_status, "predecessor reviewer status")
        if prior.unitizer_status == "unknown" or prior.reviewer_status == "unknown":
            raise CandidateScopedStageAReplayError(
                f"predecessor Stage A outcome is unknown: {candidate_id}"
            )
        if dict(prior.unitize_record).get("candidate_id") != candidate_id:
            raise CandidateScopedStageAReplayError(
                "predecessor unitize record candidate_id does not match packet"
            )
        ordered.append(prior)
    return tuple(ordered)


def _require_successor_packets(
    packets: Sequence[CandidatePacketInput],
    *,
    predecessor_candidates: Sequence[PredecessorCandidateStageA],
) -> dict[str, CandidatePacketInput]:
    predecessor_ids = [prior.packet.candidate_id for prior in predecessor_candidates]
    successor_ids = [packet.candidate_id for packet in packets]
    if len(set(successor_ids)) != len(successor_ids):
        raise CandidateScopedStageAReplayError("successor packets repeat a candidate")
    predecessor_set = set(predecessor_ids)
    successor_set = set(successor_ids)
    missing = predecessor_set - successor_set
    extra = successor_set - predecessor_set
    if missing or extra:
        raise CandidateScopedStageAReplayError(
            "successor packets must cover the predecessor candidates "
            "without subsetting or hand-authoring the exact-100 lineage"
        )
    return {packet.candidate_id: packet for packet in packets}


def _require_outcome(
    outcome: StageAStageOutcome, candidate_id: str, *, stage: str
) -> None:
    if outcome.candidate_id != candidate_id:
        raise CandidateScopedStageAReplayError(
            f"{stage} outcome candidate_id differs from the planned rerun"
        )
    _require_status(outcome.status, f"{stage} status")
    if (
        stage == "unitizer"
        and outcome.status == "settled"
        and len(outcome.records) != 1
    ):
        raise CandidateScopedStageAReplayError(
            "settled unitizer outcome must contain one candidate envelope"
        )


def _single_record(outcome: StageAStageOutcome, stage: str) -> Mapping[str, object]:
    if len(outcome.records) != 1:
        raise CandidateScopedStageAReplayError(
            f"{stage} outcome must contain one candidate envelope"
        )
    return dict(outcome.records[0])


def _require_replay_minted_plan(plan: CandidateScopedStageAPlan) -> None:
    if type(plan) is not CandidateScopedStageAPlan or not plan.is_replay_minted():
        raise CandidateScopedStageAReplayError("plan lacks replay-minted authority")
    if (
        _commit(plan.content_record(), CANDIDATE_SCOPED_STAGE_A_REPLAY_V1)
        != plan.plan_sha256
    ):
        raise CandidateScopedStageAReplayError("plan changed after classification")


def _require_replay_minted_execution(execution: CandidateScopedStageAExecution) -> None:
    if (
        type(execution) is not CandidateScopedStageAExecution
        or not execution.is_replay_minted()
    ):
        raise CandidateScopedStageAReplayError(
            "execution lacks replay-minted authority"
        )


def _require_status(status: str, label: str) -> None:
    if status not in _OUTCOME_STATUSES:
        raise CandidateScopedStageAReplayError(f"{label} is invalid")


def _require_candidate_id(candidate_id: str) -> None:
    _require_nonempty(candidate_id, "candidate_id")


def _require_nonempty(value: str, label: str) -> None:
    if not value or value.strip() != value or not value.strip():
        raise CandidateScopedStageAReplayError(f"{label} is empty")


def _require_digest(value: str, label: str) -> None:
    _digest(value, label)


def _digest(value: str, label: str) -> str:
    if _SHA256.fullmatch(value) is None:
        raise CandidateScopedStageAReplayError(f"{label} is not a SHA-256 digest")
    return value


def _byte_count(value: int) -> int:
    if isinstance(value, bool) or value < 0:
        raise CandidateScopedStageAReplayError("document byte_count is invalid")
    return value


def _elapsed_ms(started: float, finished: float) -> int:
    elapsed = finished - started
    if elapsed < 0:
        raise CandidateScopedStageAReplayError("stage clock moved backwards")
    return int(elapsed * 1000)


def _commit(record: Mapping[str, object], domain: SchemaIdentifier) -> str:
    return str(ARTIFACT_RAW_SHA256_V1.commit(record, domain=domain).digest)


def _mint_plan(**fields: object) -> CandidateScopedStageAPlan:
    plan = object.__new__(CandidateScopedStageAPlan)
    for name, value in (*fields.items(), ("_mint", _PLAN_AUTHORITY)):
        object.__setattr__(plan, name, value)
    return plan


def _mint_execution(**fields: object) -> CandidateScopedStageAExecution:
    execution = object.__new__(CandidateScopedStageAExecution)
    for name, value in (*fields.items(), ("_mint", _EXECUTION_AUTHORITY)):
        object.__setattr__(execution, name, value)
    return execution


def _mint_receipt(**fields: object) -> CandidateScopedStageAReceipt:
    receipt = object.__new__(CandidateScopedStageAReceipt)
    for name, value in (*fields.items(), ("_mint", _RECEIPT_AUTHORITY)):
        object.__setattr__(receipt, name, value)
    return receipt
