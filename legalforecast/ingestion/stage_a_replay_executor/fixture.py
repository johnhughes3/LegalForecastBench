"""Explicitly synthetic lineage adapter used only by fake-provider tests."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.candidate_scoped_stage_a_replay import (
    CandidatePacketInput,
    PacketDocument,
    ParserOutputIdentity,
    PredecessorCandidateStageA,
    packet_input_identity_sha256,
)
from legalforecast.ingestion.stage_a_replay_executor.spec import (
    ReplaySpec,
    StageAReplayExecutorError,
)


def fixture_lineage(spec: ReplaySpec) -> dict[str, Any]:
    """Build synthetic replay input after the spec's test-only marker verifies."""

    lineage = _mapping(spec.record, "lineage")
    predecessor = tuple(
        _fixture_predecessor(_mapping_value(value, "predecessor"))
        for value in _sequence(lineage, "predecessor")
    )
    successor = tuple(
        _fixture_packet(_mapping_value(value, "successor"), predecessor=False)
        for value in _sequence(lineage, "successor")
    )
    return {
        "predecessor": predecessor,
        "successor": successor,
        "predecessor_selection_sha256": _digest(
            lineage, "predecessor_selection_sha256"
        ),
        "predecessor_materialization_sha256": _digest(
            lineage, "predecessor_materialization_sha256"
        ),
        "predecessor_parser_sha256": _digest(lineage, "predecessor_parser_sha256"),
        "successor_selection_sha256": _digest(lineage, "successor_selection_sha256"),
        "successor_materialization_sha256": _digest(
            lineage, "successor_materialization_sha256"
        ),
        "successor_parser_sha256": _digest(lineage, "successor_parser_sha256"),
        "successor_parser_records": (),
        "successor_markdown_root": Path("/synthetic"),
        "successor_markdown_bytes": {},
        "require_unchanged": lambda: None,
        "evidence": {"synthetic": True},
    }


def _fixture_predecessor(
    record: Mapping[str, object],
) -> PredecessorCandidateStageA:
    expected = {
        "candidate_id",
        "case_id",
        "selection_record",
        "documents",
        "parser_outputs",
        "unitize_record",
        "unitize_audit",
        "review_flags",
        "review_audit",
        "unitizer_status",
        "reviewer_status",
    }
    if set(record) != expected:
        raise StageAReplayExecutorError("synthetic predecessor packet fields differ")
    return PredecessorCandidateStageA(
        packet=_fixture_packet(record, predecessor=True),
        unitize_record=_mapping(record, "unitize_record"),
        unitize_audit=_mapping(record, "unitize_audit"),
        review_flags=tuple(
            _mapping_value(value, "review flag")
            for value in _sequence(record, "review_flags")
        ),
        review_audit=_mapping(record, "review_audit"),
        unitizer_status=cast(Any, _text(record, "unitizer_status")),
        reviewer_status=cast(Any, _text(record, "reviewer_status")),
    )


def _fixture_packet(
    record: Mapping[str, object], *, predecessor: bool
) -> CandidatePacketInput:
    packet_fields = {
        "candidate_id",
        "case_id",
        "selection_record",
        "documents",
        "parser_outputs",
    }
    if predecessor and not packet_fields <= set(record):
        raise StageAReplayExecutorError("synthetic predecessor packet is incomplete")
    if not predecessor and set(record) != packet_fields:
        raise StageAReplayExecutorError("synthetic successor packet fields differ")
    documents = tuple(
        PacketDocument(
            source_document_id=_text(
                _mapping_value(value, "document"), "source_document_id"
            ),
            document_role=_text(_mapping_value(value, "document"), "document_role"),
            sha256=_digest(_mapping_value(value, "document"), "sha256"),
            byte_count=_integer(_mapping_value(value, "document"), "byte_count"),
        )
        for value in _sequence(record, "documents")
    )
    outputs = tuple(
        ParserOutputIdentity(
            source_document_id=_text(
                _mapping_value(value, "parser output"), "source_document_id"
            ),
            markdown_sha256=_digest(
                _mapping_value(value, "parser output"), "markdown_sha256"
            ),
            parser_reuse_identity_sha256=_digest(
                _mapping_value(value, "parser output"),
                "parser_reuse_identity_sha256",
            ),
        )
        for value in _sequence(record, "parser_outputs")
    )
    packet = CandidatePacketInput(
        candidate_id=_text(record, "candidate_id"),
        case_id=_text(record, "case_id"),
        selection_record=_mapping(record, "selection_record"),
        documents=documents,
        parser_outputs=outputs,
    )
    packet_input_identity_sha256(packet)
    return packet


def _mapping(record: Mapping[str, object], field: str) -> Mapping[str, object]:
    return _mapping_value(record.get(field), field)


def _mapping_value(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise StageAReplayExecutorError(f"{field} must be an object")
    return cast(Mapping[str, object], value)


def _sequence(record: Mapping[str, object], field: str) -> tuple[object, ...]:
    value = record.get(field)
    if not isinstance(value, list):
        raise StageAReplayExecutorError(f"{field} must be an array")
    return tuple(cast(list[object], value))


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


def _integer(record: Mapping[str, object], field: str) -> int:
    value = record.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise StageAReplayExecutorError(f"{field} must be a non-negative integer")
    return value
