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
match. Unknown rerun outcomes stop later rerun callbacks, are permanently
nonretryable, and cannot seal. Injected callbacks receive a replay-minted
rerun request and must echo its digest.
"""

from __future__ import annotations

import os
import re
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Literal, cast

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
_PREDECESSOR_AUTHORITY = object()
_PLAN_AUTHORITY = object()
_REQUEST_AUTHORITY = object()
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


@dataclass(frozen=True, slots=True, init=False)
class PredecessorStageALineage:
    """Replay-minted predecessor Stage A outputs bound to shared provider identity."""

    candidates: tuple[PredecessorCandidateStageA, ...]
    unitizer_namespace: str
    reviewer_namespace: str
    provider_caps_sha256: str
    provider_journal_path: Path
    selection_sha256: str
    materialization_sha256: str
    parser_sha256: str
    lineage_sha256: str
    _mint: object

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise CandidateScopedStageAReplayError(
            "predecessor Stage A lineage can be created only by authenticated bind"
        )

    def is_replay_minted(self) -> bool:
        return self._mint is _PREDECESSOR_AUTHORITY

    def content_record(self) -> dict[str, object]:
        return {
            "candidates": [
                _predecessor_candidate_record(candidate)
                for candidate in self.candidates
            ],
            "unitizer_namespace": self.unitizer_namespace,
            "reviewer_namespace": self.reviewer_namespace,
            "provider_caps_sha256": self.provider_caps_sha256,
            "provider_journal_path": os.path.abspath(self.provider_journal_path),
            "selection_sha256": self.selection_sha256,
            "materialization_sha256": self.materialization_sha256,
            "parser_sha256": self.parser_sha256,
        }


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
    request_sha256: str


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
    predecessor_lineage_sha256: str
    predecessor_candidates: tuple[PredecessorCandidateStageA, ...]
    successor_packets: tuple[CandidatePacketInput, ...]
    _consumed: bool
    _claim: threading.Lock
    _mint: object

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise CandidateScopedStageAReplayError(
            "candidate-scoped Stage A plan can be created only by authenticated replay"
        )

    def is_replay_minted(self) -> bool:
        return self._mint is _PLAN_AUTHORITY

    def is_consumed(self) -> bool:
        return self._consumed

    def consume(self) -> None:
        with self._claim:
            if self._consumed:
                raise CandidateScopedStageAReplayError(
                    "candidate-scoped Stage A plan already executed"
                )
            object.__setattr__(self, "_consumed", True)

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
            "predecessor_lineage_sha256": self.predecessor_lineage_sha256,
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
    execution_sha256: str
    _mint: object

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise CandidateScopedStageAReplayError(
            "candidate-scoped Stage A execution can be created only by "
            "authenticated replay"
        )

    def is_replay_minted(self) -> bool:
        return self._mint is _EXECUTION_AUTHORITY

    def content_record(self) -> dict[str, object]:
        return {
            "plan_sha256": self.plan_sha256,
            "reused_candidate_ids": list(self.reused_candidate_ids),
            "rerun_candidate_ids": list(self.rerun_candidate_ids),
            "unitize_records": [
                _jsonable_mapping(record) for record in self.unitize_records
            ],
            "unitize_audits": [
                _jsonable_mapping(record) for record in self.unitize_audits
            ],
            "review_flags": [_jsonable_mapping(record) for record in self.review_flags],
            "review_audits": [
                _jsonable_mapping(record) for record in self.review_audits
            ],
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
            "statuses": [
                {
                    "candidate_id": candidate_id,
                    "unitizer_status": unitizer_status,
                    "reviewer_status": reviewer_status,
                }
                for candidate_id, unitizer_status, reviewer_status in self.statuses
            ],
            "provider_journal_path": os.path.abspath(self.provider_journal_path),
        }


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
        if (
            _commit(self.content_record(), CANDIDATE_SCOPED_STAGE_A_REPLAY_RECEIPT_V1)
            != self.receipt_sha256
        ):
            raise CandidateScopedStageAReplayError(
                "receipt payloads changed after authenticated seal"
            )
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
            "unitize_records": [
                _jsonable_mapping(record) for record in self.unitize_records
            ],
            "unitize_audits": [
                _jsonable_mapping(record) for record in self.unitize_audits
            ],
            "review_flags": [_jsonable_mapping(record) for record in self.review_flags],
            "review_audits": [
                _jsonable_mapping(record) for record in self.review_audits
            ],
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


@dataclass(frozen=True, slots=True, init=False)
class CandidateScopedStageARerunRequest:
    """Replay-minted successor packet and provider identity for one rerun."""

    candidate_id: str
    packet: CandidatePacketInput
    packet_sha256: str
    plan_sha256: str
    unitizer_namespace: str
    reviewer_namespace: str
    provider_caps_sha256: str
    provider_journal_path: Path
    request_sha256: str
    _mint: object

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise CandidateScopedStageAReplayError(
            "candidate-scoped Stage A rerun request can be created only by "
            "authenticated replay"
        )

    def is_replay_minted(self) -> bool:
        return self._mint is _REQUEST_AUTHORITY

    def content_record(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "packet_sha256": self.packet_sha256,
            "plan_sha256": self.plan_sha256,
            "unitizer_namespace": self.unitizer_namespace,
            "reviewer_namespace": self.reviewer_namespace,
            "provider_caps_sha256": self.provider_caps_sha256,
            "provider_journal_path": os.path.abspath(self.provider_journal_path),
        }


UnitizerCallback = Callable[[CandidateScopedStageARerunRequest], StageAStageOutcome]
ReviewerCallback = Callable[
    [CandidateScopedStageARerunRequest, StageAStageOutcome], StageAStageOutcome
]
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
        "selection": _jsonable_mapping(packet.selection_record),
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


def bind_predecessor_stage_a_lineage(
    *,
    candidates: Sequence[PredecessorCandidateStageA],
    unitizer_namespace: str,
    reviewer_namespace: str,
    provider_caps_sha256: str,
    provider_journal_path: Path,
    selection_sha256: str,
    materialization_sha256: str,
    parser_sha256: str,
) -> PredecessorStageALineage:
    """Mint predecessor Stage A outputs after committing their exact payloads."""

    _require_live_namespace_pair(
        unitizer_namespace=unitizer_namespace,
        reviewer_namespace=reviewer_namespace,
    )
    frozen = _require_predecessor_candidates(candidates)
    provisional = _mint_predecessor(
        candidates=frozen,
        unitizer_namespace=unitizer_namespace,
        reviewer_namespace=reviewer_namespace,
        provider_caps_sha256=_digest(provider_caps_sha256, "provider caps digest"),
        provider_journal_path=Path(os.path.abspath(provider_journal_path)),
        selection_sha256=_digest(selection_sha256, "predecessor selection digest"),
        materialization_sha256=_digest(
            materialization_sha256, "predecessor materialization digest"
        ),
        parser_sha256=_digest(parser_sha256, "predecessor parser digest"),
        lineage_sha256="",
    )
    return _mint_predecessor(
        candidates=provisional.candidates,
        unitizer_namespace=provisional.unitizer_namespace,
        reviewer_namespace=provisional.reviewer_namespace,
        provider_caps_sha256=provisional.provider_caps_sha256,
        provider_journal_path=provisional.provider_journal_path,
        selection_sha256=provisional.selection_sha256,
        materialization_sha256=provisional.materialization_sha256,
        parser_sha256=provisional.parser_sha256,
        lineage_sha256=_commit(
            provisional.content_record(),
            CANDIDATE_SCOPED_STAGE_A_REPLAY_V1,
        ),
    )


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

    _require_replay_minted_predecessor(predecessor)
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
    predecessor_candidates = predecessor.candidates
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
        predecessor_lineage_sha256=predecessor.lineage_sha256,
        predecessor_candidates=predecessor_candidates,
        successor_packets=tuple(
            successor[candidate_id] for candidate_id in candidate_ids
        ),
        _consumed=False,
        _claim=threading.Lock(),
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
        predecessor_lineage_sha256=provisional.predecessor_lineage_sha256,
        predecessor_candidates=provisional.predecessor_candidates,
        successor_packets=provisional.successor_packets,
        _consumed=False,
        _claim=threading.Lock(),
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
    plan.consume()
    if tuple(packet.candidate_id for packet in plan.successor_packets) != (
        plan.candidate_ids
    ):
        raise CandidateScopedStageAReplayError(
            "successor packets drifted from the minted candidate order"
        )
    _require_plan_predecessor_payloads(plan)
    tick = clock or time.monotonic
    predecessor_by_id = {
        prior.packet.candidate_id: prior for prior in plan.predecessor_candidates
    }
    successor_by_id = {packet.candidate_id: packet for packet in plan.successor_packets}
    unitize_records: list[Mapping[str, object]] = []
    unitize_audits: list[Mapping[str, object]] = []
    review_flags: list[Mapping[str, object]] = []
    review_audits: list[Mapping[str, object]] = []
    timings: list[CandidateStageATiming] = []
    statuses: list[tuple[str, StageStatus, StageStatus]] = []
    attempted: set[str] = set()
    halt_reruns = False
    for decision in plan.decisions:
        prior = predecessor_by_id[decision.candidate_id]
        if decision.disposition == "reused":
            unitize_records.append(_jsonable_mapping(prior.unitize_record))
            unitize_audits.append(_jsonable_mapping(prior.unitize_audit))
            review_flags.extend(_jsonable_mapping(flag) for flag in prior.review_flags)
            review_audits.append(_jsonable_mapping(prior.review_audit))
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
        if halt_reruns:
            _append_unattempted_after_unknown(
                decision.candidate_id,
                unitize_records=unitize_records,
                unitize_audits=unitize_audits,
                review_audits=review_audits,
                timings=timings,
                statuses=statuses,
            )
            continue
        if decision.candidate_id in attempted:
            raise CandidateScopedStageAReplayError(
                f"rerun candidate was retried: {decision.candidate_id}"
            )
        attempted.add(decision.candidate_id)
        request = _mint_rerun_request(
            plan, successor_by_id[decision.candidate_id], decision=decision
        )
        started = tick()
        unitize_outcome = unitizer(request)
        after_unitizer = tick()
        _require_outcome(unitize_outcome, request, stage="unitizer")
        retained_unitize = _snapshot_outcome(unitize_outcome)
        if retained_unitize.status == "unknown":
            unitize_records.append(_single_record(retained_unitize, "unitizer"))
            unitize_audits.append(_jsonable_mapping(retained_unitize.audit))
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
            halt_reruns = True
            continue
        if retained_unitize.status in {"reconstruction_failed", "terminal_escalation"}:
            unitize_records.append(_single_record(retained_unitize, "unitizer"))
            unitize_audits.append(_jsonable_mapping(retained_unitize.audit))
            review_audits.append(
                {
                    "candidate_id": decision.candidate_id,
                    "status": retained_unitize.status,
                    "reviewer": "not_attempted_after_unitizer_terminal",
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
                (
                    decision.candidate_id,
                    retained_unitize.status,
                    retained_unitize.status,
                )
            )
            continue
        review_outcome = reviewer(request, _mutable_outcome(retained_unitize))
        finished = tick()
        _require_outcome(review_outcome, request, stage="reviewer")
        unitize_records.append(_single_record(retained_unitize, "unitizer"))
        unitize_audits.append(_jsonable_mapping(retained_unitize.audit))
        review_flags.extend(
            _jsonable_mapping(record) for record in review_outcome.records
        )
        review_audits.append(_jsonable_mapping(review_outcome.audit))
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
            (decision.candidate_id, retained_unitize.status, review_outcome.status)
        )
        if review_outcome.status == "unknown":
            halt_reruns = True
    provisional = _mint_execution(
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
        execution_sha256="",
    )
    return _mint_execution(
        plan_sha256=provisional.plan_sha256,
        reused_candidate_ids=provisional.reused_candidate_ids,
        rerun_candidate_ids=provisional.rerun_candidate_ids,
        unitize_records=provisional.unitize_records,
        unitize_audits=provisional.unitize_audits,
        review_flags=provisional.review_flags,
        review_audits=provisional.review_audits,
        timings=provisional.timings,
        statuses=provisional.statuses,
        provider_journal_path=provisional.provider_journal_path,
        execution_sha256=_commit(
            provisional.content_record(),
            CANDIDATE_SCOPED_STAGE_A_REPLAY_RECEIPT_V1,
        ),
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
    frozen = _freeze_receipt_payloads(provisional)
    return _mint_receipt(
        schema_version=frozen.schema_version,
        plan_sha256=frozen.plan_sha256,
        successor_selection_sha256=frozen.successor_selection_sha256,
        successor_materialization_sha256=frozen.successor_materialization_sha256,
        successor_parser_sha256=frozen.successor_parser_sha256,
        unitizer_namespace=frozen.unitizer_namespace,
        reviewer_namespace=frozen.reviewer_namespace,
        provider_caps_sha256=frozen.provider_caps_sha256,
        provider_journal_path=frozen.provider_journal_path,
        candidate_ids=frozen.candidate_ids,
        reused_candidate_ids=frozen.reused_candidate_ids,
        rerun_candidate_ids=frozen.rerun_candidate_ids,
        unitize_records=frozen.unitize_records,
        unitize_audits=frozen.unitize_audits,
        review_flags=frozen.review_flags,
        review_audits=frozen.review_audits,
        timings=frozen.timings,
        receipt_sha256=_commit(
            frozen.content_record(),
            CANDIDATE_SCOPED_STAGE_A_REPLAY_RECEIPT_V1,
        ),
    )


def _freeze_receipt_payloads(
    receipt: CandidateScopedStageAReceipt,
) -> CandidateScopedStageAReceipt:
    return _mint_receipt(
        schema_version=receipt.schema_version,
        plan_sha256=receipt.plan_sha256,
        successor_selection_sha256=receipt.successor_selection_sha256,
        successor_materialization_sha256=receipt.successor_materialization_sha256,
        successor_parser_sha256=receipt.successor_parser_sha256,
        unitizer_namespace=receipt.unitizer_namespace,
        reviewer_namespace=receipt.reviewer_namespace,
        provider_caps_sha256=receipt.provider_caps_sha256,
        provider_journal_path=receipt.provider_journal_path,
        candidate_ids=receipt.candidate_ids,
        reused_candidate_ids=receipt.reused_candidate_ids,
        rerun_candidate_ids=receipt.rerun_candidate_ids,
        unitize_records=tuple(
            _freeze_mapping(record) for record in receipt.unitize_records
        ),
        unitize_audits=tuple(
            _freeze_mapping(record) for record in receipt.unitize_audits
        ),
        review_flags=tuple(_freeze_mapping(record) for record in receipt.review_flags),
        review_audits=tuple(
            _freeze_mapping(record) for record in receipt.review_audits
        ),
        timings=receipt.timings,
        receipt_sha256=receipt.receipt_sha256,
    )


def _require_replay_minted_predecessor(predecessor: PredecessorStageALineage) -> None:
    if (
        type(predecessor) is not PredecessorStageALineage
        or not predecessor.is_replay_minted()
    ):
        raise CandidateScopedStageAReplayError(
            "predecessor Stage A lineage lacks replay-minted authority"
        )
    if (
        _commit(predecessor.content_record(), CANDIDATE_SCOPED_STAGE_A_REPLAY_V1)
        != predecessor.lineage_sha256
    ):
        raise CandidateScopedStageAReplayError(
            "predecessor Stage A lineage changed after bind"
        )


def _predecessor_candidate_record(
    candidate: PredecessorCandidateStageA,
) -> dict[str, object]:
    return {
        "packet_sha256": packet_input_identity_sha256(candidate.packet),
        "candidate_id": candidate.packet.candidate_id,
        "case_id": candidate.packet.case_id,
        "unitize_record": _jsonable_mapping(candidate.unitize_record),
        "unitize_audit": _jsonable_mapping(candidate.unitize_audit),
        "review_flags": [_jsonable_mapping(flag) for flag in candidate.review_flags],
        "review_audit": _jsonable_mapping(candidate.review_audit),
        "unitizer_status": candidate.unitizer_status,
        "reviewer_status": candidate.reviewer_status,
    }


def _freeze_predecessor_candidate(
    prior: PredecessorCandidateStageA,
) -> PredecessorCandidateStageA:
    return PredecessorCandidateStageA(
        packet=_freeze_packet(prior.packet),
        unitize_record=_freeze_mapping(prior.unitize_record),
        unitize_audit=_freeze_mapping(prior.unitize_audit),
        review_flags=tuple(_freeze_mapping(flag) for flag in prior.review_flags),
        review_audit=_freeze_mapping(prior.review_audit),
        unitizer_status=prior.unitizer_status,
        reviewer_status=prior.reviewer_status,
    )


def _freeze_packet(packet: CandidatePacketInput) -> CandidatePacketInput:
    return CandidatePacketInput(
        candidate_id=packet.candidate_id,
        case_id=packet.case_id,
        selection_record=_freeze_mapping(packet.selection_record),
        documents=packet.documents,
        parser_outputs=packet.parser_outputs,
    )


def _freeze_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    copied = _require_str_mapping(value)
    return MappingProxyType({key: _freeze_value(item) for key, item in copied.items()})


def _freeze_value(value: object) -> object:
    copied = _copy_str_mapping(value)
    if copied is not None:
        return MappingProxyType(
            {key: _freeze_value(item) for key, item in copied.items()}
        )
    sequence = _sequence_items(value)
    if sequence is not None:
        return tuple(_freeze_value(item) for item in sequence)
    return value


def _jsonable_mapping(value: Mapping[str, object]) -> dict[str, object]:
    copied = _require_str_mapping(value)
    return {key: _jsonable_value(item) for key, item in copied.items()}


def _jsonable_value(value: object) -> object:
    copied = _copy_str_mapping(value)
    if copied is not None:
        return {key: _jsonable_value(item) for key, item in copied.items()}
    sequence = _sequence_items(value)
    if sequence is not None:
        return [_jsonable_value(item) for item in sequence]
    return value


def _require_str_mapping(value: Mapping[str, object]) -> dict[str, object]:
    copied = _copy_str_mapping(value)
    if copied is None:
        raise CandidateScopedStageAReplayError("payload is not a mapping")
    return copied


def _copy_str_mapping(value: object) -> dict[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    typed = cast(Mapping[object, object], value)
    copied: dict[str, object] = {}
    for raw_key in typed:
        if not isinstance(raw_key, str):
            raise CandidateScopedStageAReplayError("mapping key is not a string")
        copied[raw_key] = typed[raw_key]
    return copied


def _sequence_items(value: object) -> tuple[object, ...] | None:
    if isinstance(value, list):
        return tuple(cast(list[object], value))
    if isinstance(value, tuple):
        return cast(tuple[object, ...], value)
    return None


def _snapshot_outcome(outcome: StageAStageOutcome) -> StageAStageOutcome:
    return StageAStageOutcome(
        candidate_id=outcome.candidate_id,
        records=tuple(_freeze_mapping(record) for record in outcome.records),
        audit=_freeze_mapping(outcome.audit),
        status=outcome.status,
        request_sha256=outcome.request_sha256,
    )


def _mutable_outcome(outcome: StageAStageOutcome) -> StageAStageOutcome:
    return StageAStageOutcome(
        candidate_id=outcome.candidate_id,
        records=tuple(_jsonable_mapping(record) for record in outcome.records),
        audit=_jsonable_mapping(outcome.audit),
        status=outcome.status,
        request_sha256=outcome.request_sha256,
    )


def _require_plan_predecessor_payloads(plan: CandidateScopedStageAPlan) -> None:
    payload = {
        "candidates": [
            _predecessor_candidate_record(candidate)
            for candidate in plan.predecessor_candidates
        ],
        "unitizer_namespace": plan.unitizer_namespace,
        "reviewer_namespace": plan.reviewer_namespace,
        "provider_caps_sha256": plan.provider_caps_sha256,
        "provider_journal_path": os.path.abspath(plan.provider_journal_path),
        "selection_sha256": plan.predecessor_selection_sha256,
        "materialization_sha256": plan.predecessor_materialization_sha256,
        "parser_sha256": plan.predecessor_parser_sha256,
    }
    if (
        _commit(payload, CANDIDATE_SCOPED_STAGE_A_REPLAY_V1)
        != plan.predecessor_lineage_sha256
    ):
        raise CandidateScopedStageAReplayError(
            "predecessor payloads changed after classification"
        )


def _mint_rerun_request(
    plan: CandidateScopedStageAPlan,
    packet: CandidatePacketInput,
    *,
    decision: CandidateReplayDecision,
) -> CandidateScopedStageARerunRequest:
    if packet.candidate_id != decision.candidate_id:
        raise CandidateScopedStageAReplayError(
            "successor packet candidate_id differs from the planned rerun"
        )
    packet_sha256 = packet_input_identity_sha256(packet)
    if packet_sha256 != decision.successor_packet_sha256:
        raise CandidateScopedStageAReplayError(
            "successor packet identity drifted from the minted plan"
        )
    provisional = _mint_request(
        candidate_id=decision.candidate_id,
        packet=_freeze_packet(packet),
        packet_sha256=packet_sha256,
        plan_sha256=plan.plan_sha256,
        unitizer_namespace=plan.unitizer_namespace,
        reviewer_namespace=plan.reviewer_namespace,
        provider_caps_sha256=plan.provider_caps_sha256,
        provider_journal_path=plan.provider_journal_path,
        request_sha256="",
    )
    return _mint_request(
        candidate_id=provisional.candidate_id,
        packet=provisional.packet,
        packet_sha256=provisional.packet_sha256,
        plan_sha256=provisional.plan_sha256,
        unitizer_namespace=provisional.unitizer_namespace,
        reviewer_namespace=provisional.reviewer_namespace,
        provider_caps_sha256=provisional.provider_caps_sha256,
        provider_journal_path=provisional.provider_journal_path,
        request_sha256=_commit(
            provisional.content_record(),
            CANDIDATE_SCOPED_STAGE_A_REPLAY_V1,
        ),
    )


def _append_unattempted_after_unknown(
    candidate_id: str,
    *,
    unitize_records: list[Mapping[str, object]],
    unitize_audits: list[Mapping[str, object]],
    review_audits: list[Mapping[str, object]],
    timings: list[CandidateStageATiming],
    statuses: list[tuple[str, StageStatus, StageStatus]],
) -> None:
    unitize_records.append({"candidate_id": candidate_id})
    unitize_audits.append({"candidate_id": candidate_id, "status": "unknown"})
    review_audits.append(
        {
            "candidate_id": candidate_id,
            "status": "not_attempted_after_unknown",
        }
    )
    timings.append(
        CandidateStageATiming(
            candidate_id=candidate_id,
            disposition="rerun",
            elapsed_ms=0,
            unitizer_elapsed_ms=0,
            reviewer_elapsed_ms=0,
        )
    )
    statuses.append((candidate_id, "unknown", "unknown"))


def _require_nested_candidate(
    record: Mapping[str, object],
    candidate_id: str,
    *,
    label: str,
    required: bool = True,
) -> None:
    nested = dict(record).get("candidate_id")
    if nested is None:
        if required:
            raise CandidateScopedStageAReplayError(f"{label} lacks candidate_id")
        return
    if nested != candidate_id:
        raise CandidateScopedStageAReplayError(
            f"{label} candidate_id differs from the planned candidate"
        )


def _require_nested_status(
    record: Mapping[str, object], status: str, *, label: str
) -> None:
    nested = dict(record).get("status")
    if nested is not None and nested != status:
        raise CandidateScopedStageAReplayError(
            f"{label} status differs from the authenticated outcome"
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
        _require_nested_candidate(
            prior.unitize_audit, candidate_id, label="predecessor unitize audit"
        )
        _require_nested_status(
            prior.unitize_audit,
            prior.unitizer_status,
            label="predecessor unitize audit",
        )
        for flag in prior.review_flags:
            _require_nested_candidate(
                flag, candidate_id, label="predecessor review flag", required=False
            )
        _require_nested_candidate(
            prior.review_audit, candidate_id, label="predecessor review audit"
        )
        _require_nested_status(
            prior.review_audit,
            prior.reviewer_status,
            label="predecessor review audit",
        )
        ordered.append(_freeze_predecessor_candidate(prior))
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
    return {packet.candidate_id: _freeze_packet(packet) for packet in packets}


def _require_outcome(
    outcome: StageAStageOutcome,
    request: CandidateScopedStageARerunRequest,
    *,
    stage: str,
) -> None:
    if outcome.candidate_id != request.candidate_id:
        raise CandidateScopedStageAReplayError(
            f"{stage} outcome candidate_id differs from the planned rerun"
        )
    if outcome.request_sha256 != request.request_sha256:
        raise CandidateScopedStageAReplayError(
            f"{stage} outcome request digest differs from the minted rerun request"
        )
    _require_status(outcome.status, f"{stage} status")
    for record in outcome.records:
        _require_nested_candidate(
            record,
            request.candidate_id,
            label=f"{stage} record",
            required=stage == "unitizer",
        )
    _require_nested_candidate(
        outcome.audit, request.candidate_id, label=f"{stage} audit"
    )
    _require_nested_status(outcome.audit, outcome.status, label=f"{stage} audit")
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
    return _jsonable_mapping(outcome.records[0])


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
    if (
        _commit(execution.content_record(), CANDIDATE_SCOPED_STAGE_A_REPLAY_RECEIPT_V1)
        != execution.execution_sha256
    ):
        raise CandidateScopedStageAReplayError(
            "execution payloads changed after authenticated replay"
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


def _mint_predecessor(**fields: object) -> PredecessorStageALineage:
    lineage = object.__new__(PredecessorStageALineage)
    for name, value in (*fields.items(), ("_mint", _PREDECESSOR_AUTHORITY)):
        object.__setattr__(lineage, name, value)
    return lineage


def _mint_plan(**fields: object) -> CandidateScopedStageAPlan:
    plan = object.__new__(CandidateScopedStageAPlan)
    for name, value in (*fields.items(), ("_mint", _PLAN_AUTHORITY)):
        object.__setattr__(plan, name, value)
    return plan


def _mint_request(**fields: object) -> CandidateScopedStageARerunRequest:
    request = object.__new__(CandidateScopedStageARerunRequest)
    for name, value in (*fields.items(), ("_mint", _REQUEST_AUTHORITY)):
        object.__setattr__(request, name, value)
    return request


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
