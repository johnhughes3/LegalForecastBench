"""Verifier-owned predecessor and successor inputs for Stage A replay."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from legalforecast.contracts import (
    ARTIFACT_RAW_SHA256_V1,
    CANDIDATE_SCOPED_STAGE_A_REPLAY_V1,
)
from legalforecast.ingestion.candidate_scoped_stage_a_replay import (
    CandidatePacketInput,
    PacketDocument,
    ParserOutputIdentity,
    PredecessorCandidateStageA,
    packet_input_identity_sha256,
)
from legalforecast.ingestion.stage_a_replay_executor.contract import (
    parse_strict_jsonl,
)
from legalforecast.ingestion.stage_a_replay_executor.repair import (
    verify_repair_receipt,
    verify_repair_scope,
)
from legalforecast.ingestion.stage_a_replay_executor.spec import (
    ReplaySpec,
    StageAReplayExecutorError,
)
from legalforecast.ingestion.successor_rerun_proposal import (
    verified_documents_from_records,
)


@dataclass(frozen=True, slots=True)
class VerifiedReplayLineage:
    """Complete predecessor cohort plus independently verified successor cohort."""

    predecessor: tuple[PredecessorCandidateStageA, ...]
    successor: tuple[CandidatePacketInput, ...]
    predecessor_selection_sha256: str
    predecessor_materialization_sha256: str
    predecessor_parser_sha256: str
    successor_selection_sha256: str
    successor_materialization_sha256: str
    successor_parser_sha256: str
    successor_parser_records: tuple[Mapping[str, Any], ...]
    successor_markdown_root: Path
    successor_markdown_bytes: Mapping[str, bytes] | None
    require_unchanged: Callable[[], None]
    evidence: Mapping[str, object]


class _VerifiedParseLineage(Protocol):
    @property
    def selection_records(self) -> Sequence[Mapping[str, Any]]: ...

    @property
    def download_records(self) -> Sequence[Mapping[str, Any]]: ...

    @property
    def parser_records(self) -> Sequence[Mapping[str, Any]]: ...

    @property
    def document_root(self) -> Path: ...

    @property
    def markdown_root(self) -> Path: ...

    @property
    def markdown_bytes(self) -> Mapping[str, bytes]: ...


class _VerifiedStageA(Protocol):
    @property
    def raw_prediction_unit_records(self) -> Sequence[Mapping[str, object]]: ...

    @property
    def unitization_audit_records(self) -> Sequence[Mapping[str, object]]: ...

    @property
    def structural_review_audit_records(
        self,
    ) -> Sequence[Mapping[str, object]]: ...

    @property
    def structural_flag_records(self) -> Sequence[Mapping[str, object]]: ...


def verify_replay_lineage(spec: ReplaySpec) -> VerifiedReplayLineage:
    """Resolve fixture inputs or replay every production artifact verifier."""

    if spec.synthetic_fixture:
        from legalforecast.ingestion.stage_a_replay_executor.fixture import (
            fixture_lineage,
        )

        return VerifiedReplayLineage(**fixture_lineage(spec))
    try:
        _verify_cycle_root(spec)
        return _production_lineage(spec)
    except StageAReplayExecutorError:
        raise
    except Exception as exc:
        raise StageAReplayExecutorError(
            f"authenticated Stage A lineage preflight failed: {exc}"
        ) from exc


def _production_lineage(spec: ReplaySpec) -> VerifiedReplayLineage:
    from legalforecast.ingestion.stage_a_lineage_verification import (
        StageALineageInputs,
        require_stage_a_lineage_unchanged,
        require_stage_a_parse_lineage_unchanged,
        verify_stage_a_packet_authority,
        verify_stage_a_parse_lineage_uncached,
        verify_stage_a_unitization_run_card,
    )

    lineage_record = _mapping(spec.record, "lineage")
    prior = _mapping(lineage_record, "predecessor")
    successor = _mapping(lineage_record, "successor")
    controlled_root = _optional_path(prior, "controlled_private_root")
    initialization_receipt = _optional_path(prior, "initialization_receipt_path")
    unitization_card = _path(prior, "unitization_run_card_path")
    raw_units = _path(prior, "raw_prediction_units_path")
    unit_audit = _path(prior, "unitization_audit_path")
    original_review = _path(prior, "original_review_path")
    predecessor_lineage = verify_stage_a_unitization_run_card(
        unitization_card,
        expected_prediction_units_path=raw_units,
        expected_review_queue_path=original_review,
        expected_audit_path=unit_audit,
        controlled_private_root=controlled_root,
        initialization_receipt_path=initialization_receipt,
    )
    if (
        predecessor_lineage.provider_journal_path.resolve()
        != spec.provider_journal_path
    ):
        raise StageAReplayExecutorError(
            "predecessor Stage A provider journal differs from replay-spec"
        )
    if predecessor_lineage.provider_caps_sha256 != spec.provider_caps_sha256:
        raise StageAReplayExecutorError(
            "predecessor Stage A provider caps differ from replay-spec"
        )
    if predecessor_lineage.registry_entry.registry_key != spec.model_ids["unitizer"]:
        raise StageAReplayExecutorError(
            "predecessor Stage A unitizer model differs from replay-spec"
        )

    finalized_path = _path(prior, "finalized_prediction_units_path")
    finalized_records = parse_strict_jsonl(
        _read_regular(finalized_path, "finalized Stage A")
    )
    stage_a = verify_stage_a_packet_authority(
        selection_records=predecessor_lineage.selection_records,
        parser_records=predecessor_lineage.parser_records,
        raw_prediction_units_path=raw_units,
        unitization_audit_path=unit_audit,
        unitization_run_card_path=unitization_card,
        unitization_provider_journal_path=spec.provider_journal_path,
        original_review_path=original_review,
        structural_flags_path=_path(prior, "structural_flags_path"),
        structural_review_audit_path=_path(prior, "structural_review_audit_path"),
        structural_review_run_card_path=_path(prior, "structural_review_run_card_path"),
        structural_review_provider_journal_path=spec.provider_journal_path,
        structural_review_registry_path=_path(prior, "structural_review_registry_path"),
        structural_review_model_key=_text(prior, "structural_review_model_key"),
        merged_review_path=_path(prior, "merged_review_path"),
        finalized_prediction_unit_records=finalized_records,
        finalized_prediction_units_path=finalized_path,
        adjudications_path=_path(prior, "adjudications_path"),
        apply_unitization_run_card_path=_path(prior, "apply_unitization_run_card_path"),
        controlled_private_root=controlled_root,
        initialization_receipt_path=initialization_receipt,
    )
    if _text(prior, "structural_review_model_key") != spec.model_ids["reviewer"]:
        raise StageAReplayExecutorError(
            "predecessor Stage A reviewer model differs from replay-spec"
        )

    successor_inputs = StageALineageInputs(
        selection=_path(successor, "selection_path"),
        selection_run_card=_path(successor, "selection_run_card_path"),
        download_manifest=_path(successor, "download_manifest_path"),
        disclosure_clearance=_path(successor, "disclosure_clearance_path"),
        materialization_run_card=_path(successor, "materialization_run_card_path"),
        document_root=_path(successor, "document_root"),
        parse_requests=_path(successor, "parse_requests_path"),
        parser_manifest=_path(successor, "parser_manifest_path"),
        parser_run_card=_path(successor, "parser_run_card_path"),
        controlled_private_root=_optional_path(successor, "controlled_private_root"),
        purchase_ledger_initialization_receipt=_optional_path(
            successor, "initialization_receipt_path"
        ),
    )
    successor_parse = verify_stage_a_parse_lineage_uncached(
        successor_inputs, markdown_root=_path(successor, "markdown_root")
    )
    if predecessor_lineage.cohort_cycle_id != spec.cycle_id:
        raise StageAReplayExecutorError(
            "predecessor Stage A cycle differs from replay-spec"
        )
    if successor_parse.cohort_cycle_id != spec.cycle_id:
        raise StageAReplayExecutorError(
            "successor Stage A cycle differs from replay-spec"
        )

    predecessor_packets = _packets_from_verified_parse(predecessor_lineage)
    successor_packets = _packets_from_verified_parse(successor_parse)
    if len(predecessor_packets) != 100:
        raise StageAReplayExecutorError(
            "production predecessor Stage A lineage is not the exact-100 cohort"
        )
    if tuple(packet.candidate_id for packet in successor_packets) != tuple(
        packet.candidate_id for packet in predecessor_packets
    ):
        raise StageAReplayExecutorError(
            "successor packets must preserve the complete predecessor order"
        )
    predecessors = _predecessor_stage_a(predecessor_packets, stage_a)
    repair_evidence = verify_repair_receipt(_mapping(lineage_record, "repair_receipt"))
    verify_repair_scope(spec, repair_evidence, successor_packets)
    predecessor_digests = _lineage_component_digests(
        predecessor_lineage.input_commitments
    )
    successor_digests = _lineage_component_digests(successor_parse.input_commitments)

    def unchanged() -> None:
        require_stage_a_lineage_unchanged(predecessor_lineage)
        require_stage_a_parse_lineage_unchanged(successor_parse)

    unchanged()
    return VerifiedReplayLineage(
        predecessor=predecessors,
        successor=successor_packets,
        predecessor_selection_sha256=predecessor_digests[0],
        predecessor_materialization_sha256=predecessor_digests[1],
        predecessor_parser_sha256=predecessor_digests[2],
        successor_selection_sha256=successor_digests[0],
        successor_materialization_sha256=successor_digests[1],
        successor_parser_sha256=successor_digests[2],
        successor_parser_records=tuple(successor_parse.parser_records),
        successor_markdown_root=successor_parse.markdown_root,
        successor_markdown_bytes=dict(successor_parse.markdown_bytes),
        require_unchanged=unchanged,
        evidence={
            "cycle_root_identity_sha256": _digest(
                lineage_record, "active_root_identity_sha256"
            ),
            "predecessor_input_commitments": dict(
                predecessor_lineage.input_commitments
            ),
            "successor_input_commitments": dict(successor_parse.input_commitments),
            "repair_receipt": repair_evidence,
        },
    )


def _packets_from_verified_parse(
    lineage: _VerifiedParseLineage,
) -> tuple[CandidatePacketInput, ...]:
    selection_records = lineage.selection_records
    download_records = lineage.download_records
    parser_records = lineage.parser_records
    documents = verified_documents_from_records(
        selection_records,
        download_records,
        document_root=lineage.document_root,
    )
    docs_by_candidate: dict[str, list[PacketDocument]] = defaultdict(list)
    for document in documents:
        docs_by_candidate[document.candidate_id].append(
            PacketDocument(
                source_document_id=document.source_document_id,
                document_role=document.document_role,
                sha256=document.sha256,
                byte_count=document.byte_count,
            )
        )
    parser_by_candidate: dict[str, list[ParserOutputIdentity]] = defaultdict(list)
    markdown_root = lineage.markdown_root
    markdown_bytes = lineage.markdown_bytes
    for record in parser_records:
        candidate_id = _text(record, "candidate_id")
        source_document_id = _text(record, "source_document_id")
        raw_path = Path(_text(record, "markdown_path"))
        markdown_path = raw_path if raw_path.is_absolute() else markdown_root / raw_path
        relative = (
            markdown_path.resolve().relative_to(markdown_root.resolve()).as_posix()
        )
        payload = markdown_bytes[relative]
        markdown_sha = hashlib.sha256(payload).hexdigest()
        expected = _text(
            _mapping(record, "extracted_text"), "text_sha256"
        ).removeprefix("sha256:")
        if expected != markdown_sha:
            raise StageAReplayExecutorError(
                "verified parser Markdown differs for "
                f"{candidate_id}/{source_document_id}"
            )
        parser_identity = str(
            ARTIFACT_RAW_SHA256_V1.commit(
                {"parser_record": dict(record), "markdown_sha256": markdown_sha},
                domain=CANDIDATE_SCOPED_STAGE_A_REPLAY_V1,
            ).digest
        )
        parser_by_candidate[candidate_id].append(
            ParserOutputIdentity(
                source_document_id=source_document_id,
                markdown_sha256=markdown_sha,
                parser_reuse_identity_sha256=parser_identity,
            )
        )
    packets: list[CandidatePacketInput] = []
    for selection in selection_records:
        candidate_id = _text(selection, "candidate_id")
        packet = CandidatePacketInput(
            candidate_id=candidate_id,
            case_id=_text(selection, "case_id"),
            selection_record=dict(selection),
            documents=tuple(
                sorted(
                    docs_by_candidate[candidate_id],
                    key=lambda item: item.source_document_id,
                )
            ),
            parser_outputs=tuple(
                sorted(
                    parser_by_candidate[candidate_id],
                    key=lambda item: item.source_document_id,
                )
            ),
        )
        packet_input_identity_sha256(packet)
        packets.append(packet)
    return tuple(packets)


def _predecessor_stage_a(
    packets: Sequence[CandidatePacketInput], replay: _VerifiedStageA
) -> tuple[PredecessorCandidateStageA, ...]:
    raw_by_candidate = _unique_by_candidate(
        replay.raw_prediction_unit_records, "raw unit"
    )
    unit_audit = _unique_by_candidate(replay.unitization_audit_records, "unit audit")
    review_audit = _unique_by_candidate(
        replay.structural_review_audit_records, "review audit"
    )
    flags: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for record in replay.structural_flag_records:
        flags[_text(record, "candidate_id")].append(record)
    result: list[PredecessorCandidateStageA] = []
    for packet in packets:
        candidate_id = packet.candidate_id
        unit = unit_audit[candidate_id]
        review = review_audit[candidate_id]
        unit_status = _replay_status(unit, stage="unitizer")
        review_status = (
            unit_status
            if unit_status in {"reconstruction_failed", "terminal_escalation"}
            else _replay_status(review, stage="reviewer")
        )
        result.append(
            PredecessorCandidateStageA(
                packet=packet,
                unitize_record=raw_by_candidate[candidate_id],
                unitize_audit=unit,
                review_flags=tuple(flags[candidate_id]),
                review_audit=review,
                unitizer_status=cast(Any, unit_status),
                reviewer_status=cast(Any, review_status),
            )
        )
    return tuple(result)


def _unique_by_candidate(
    records: Sequence[Mapping[str, object]], label: str
) -> dict[str, Mapping[str, object]]:
    result: dict[str, Mapping[str, object]] = {}
    for record in records:
        candidate_id = _text(record, "candidate_id")
        if candidate_id in result:
            raise StageAReplayExecutorError(f"{label} repeats candidate {candidate_id}")
        result[candidate_id] = record
    return result


def _replay_status(record: Mapping[str, object], *, stage: str) -> str:
    status = _text(record, "status")
    live = (
        {"succeeded", "adjudication_pending", "settled"}
        if stage == "unitizer"
        else {"passed", "flags_pending", "settled"}
    )
    if status in live:
        return "settled"
    if status in {"reconstruction_failed", "terminal_escalation"}:
        return status
    raise StageAReplayExecutorError(
        f"predecessor {stage} status is not terminal: {status}"
    )


def _lineage_component_digests(
    commitments: Mapping[str, object],
) -> tuple[str, str, str]:
    groups = (
        ("selection", "selection_run_card"),
        (
            "download_manifest",
            "disclosure_clearance",
            "materialization_run_card",
            "document_tree",
        ),
        ("parse_requests", "parser_manifest", "parser_run_card", "markdown_tree"),
    )
    result: list[str] = []
    for names in groups:
        if any(name not in commitments for name in names):
            missing = next(name for name in names if name not in commitments)
            raise StageAReplayExecutorError(
                f"verified Stage A lineage lacks commitment {missing}"
            )
        result.append(
            str(
                ARTIFACT_RAW_SHA256_V1.commit(
                    {name: commitments[name] for name in names},
                    domain=CANDIDATE_SCOPED_STAGE_A_REPLAY_V1,
                ).digest
            )
        )
    return result[0], result[1], result[2]


def _verify_cycle_root(spec: ReplaySpec) -> None:
    from legalforecast.ingestion.cycle_lineage_index import locate_cycle_lineage

    lineage = _mapping(spec.record, "lineage")
    located = locate_cycle_lineage(
        index_path=_path(lineage, "index_path"), cycle_id=spec.cycle_id
    )
    if located.get("verification") != "VERIFIED":
        raise StageAReplayExecutorError("cycle lineage did not verify")
    if located.get("root_identity_sha256") != _digest(
        lineage, "active_root_identity_sha256"
    ):
        raise StageAReplayExecutorError(
            "cycle lineage root identity differs from replay-spec"
        )


def _read_regular(path: Path, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise StageAReplayExecutorError(f"{label} is not a regular file: {path}")
    return path.read_bytes()


def _mapping(record: Mapping[str, object], field: str) -> Mapping[str, object]:
    return _mapping_value(record.get(field), field)


def _mapping_value(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise StageAReplayExecutorError(f"{field} must be an object")
    return cast(Mapping[str, object], value)


def _path(record: Mapping[str, object], field: str) -> Path:
    return Path(_text(record, field))


def _optional_path(record: Mapping[str, object], field: str) -> Path | None:
    return None if record.get(field) is None else _path(record, field)


def _text(record: Mapping[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise StageAReplayExecutorError(f"{field} must be non-empty text")
    return value


def _digest(record: Mapping[str, object], field: str) -> str:
    value = _text(record, field).removeprefix("sha256:")
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise StageAReplayExecutorError(f"{field} must be a lowercase SHA-256 digest")
    return value
