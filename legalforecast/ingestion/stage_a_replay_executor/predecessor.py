"""Exact-byte authentication for predecessor Stage A prompt namespaces."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from legalforecast.ingestion.stage_a_lineage_verification import (
    StageAUnitizationLineage,
    verify_stage_a_review_run_card,
    verify_stage_a_unitization_run_card,
)
from legalforecast.ingestion.stage_a_replay_executor.spec import (
    REVIEWER_CONFIG_NAMESPACE,
    UNITIZER_CONFIG_NAMESPACE,
    StageAReplayExecutorError,
)


@dataclass(frozen=True, slots=True)
class PredecessorRunCardPaths:
    """Paths whose identities are authenticated by the predecessor cards."""

    unitization_card: Path
    raw_units: Path
    unitization_audit: Path
    original_review: Path
    structural_flags: Path
    structural_audit: Path
    structural_card: Path
    structural_registry: Path
    structural_model: str
    merged_review: Path


@dataclass(frozen=True, slots=True)
class VerifiedPredecessorRunCards:
    """Authenticated predecessor lineage and exact prompt namespaces."""

    lineage: StageAUnitizationLineage
    unitizer_namespace: str
    reviewer_namespace: str
    paths: PredecessorRunCardPaths
    require_unchanged: Callable[[], None]


def verify_predecessor_run_cards(
    *,
    record: Mapping[str, object],
    controlled_private_root: Path | None,
    initialization_receipt_path: Path | None,
) -> VerifiedPredecessorRunCards:
    """Verify both run cards against one captured exact-byte snapshot."""

    paths = _paths(record)
    unitizer_bytes = _read_run_card(paths.unitization_card, "unitizer")
    reviewer_bytes = _read_run_card(paths.structural_card, "reviewer")
    captured = {
        str(paths.unitization_card.resolve()): unitizer_bytes,
        str(paths.structural_card.resolve()): reviewer_bytes,
    }
    lineage = verify_stage_a_unitization_run_card(
        paths.unitization_card,
        expected_prediction_units_path=paths.raw_units,
        expected_review_queue_path=paths.original_review,
        expected_audit_path=paths.unitization_audit,
        controlled_private_root=controlled_private_root,
        initialization_receipt_path=initialization_receipt_path,
        captured_input_bytes=captured,
    )
    verify_stage_a_review_run_card(
        paths.structural_card,
        lineage=lineage,
        llm_unitization_run_card_path=paths.unitization_card,
        expected_review_queue_path=paths.merged_review,
        expected_structural_flags_path=paths.structural_flags,
        expected_audit_path=paths.structural_audit,
        expected_registry_path=paths.structural_registry,
        expected_model_key=paths.structural_model,
        captured_input_bytes=captured,
    )
    unitizer_namespace, reviewer_namespace = require_frozen_predecessor_namespaces(
        unitizer_bytes, reviewer_bytes
    )

    def unchanged() -> None:
        if _read_run_card(paths.unitization_card, "unitizer") != unitizer_bytes:
            raise StageAReplayExecutorError(
                "predecessor Stage A unitizer run card changed after verification"
            )
        if _read_run_card(paths.structural_card, "reviewer") != reviewer_bytes:
            raise StageAReplayExecutorError(
                "predecessor Stage A reviewer run card changed after verification"
            )

    return VerifiedPredecessorRunCards(
        lineage=lineage,
        unitizer_namespace=unitizer_namespace,
        reviewer_namespace=reviewer_namespace,
        paths=paths,
        require_unchanged=unchanged,
    )


def require_frozen_predecessor_namespaces(
    unitizer_run_card_bytes: bytes, reviewer_run_card_bytes: bytes
) -> tuple[str, str]:
    """Extract the frozen pair only from the exact authenticated card bytes."""

    unitizer = _namespace(unitizer_run_card_bytes, "unitizer")
    reviewer = _namespace(reviewer_run_card_bytes, "reviewer")
    if unitizer != UNITIZER_CONFIG_NAMESPACE:
        raise StageAReplayExecutorError(
            "predecessor Stage A unitizer namespace is not frozen v5"
        )
    if reviewer != REVIEWER_CONFIG_NAMESPACE:
        raise StageAReplayExecutorError(
            "predecessor Stage A reviewer namespace is not frozen v4"
        )
    return unitizer, reviewer


def _namespace(payload: bytes, stage: str) -> str:
    try:
        value: object = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StageAReplayExecutorError(
            f"predecessor Stage A {stage} run card is invalid JSON"
        ) from exc
    if not isinstance(value, Mapping):
        raise StageAReplayExecutorError(
            f"predecessor Stage A {stage} run card must be an object"
        )
    execution = cast(Mapping[str, object], value).get("model_execution")
    if not isinstance(execution, Mapping):
        raise StageAReplayExecutorError(
            f"predecessor Stage A {stage} run card lacks model execution"
        )
    namespace = cast(Mapping[str, object], execution).get("provider_attempt_namespace")
    if not isinstance(namespace, str) or not namespace:
        raise StageAReplayExecutorError(
            f"predecessor Stage A {stage} namespace is invalid"
        )
    return namespace


def _read_run_card(path: Path, stage: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise StageAReplayExecutorError(
            f"predecessor Stage A {stage} run card is not a regular file"
        )
    return path.read_bytes()


def _paths(record: Mapping[str, object]) -> PredecessorRunCardPaths:
    return PredecessorRunCardPaths(
        unitization_card=_path(record, "unitization_run_card_path"),
        raw_units=_path(record, "raw_prediction_units_path"),
        unitization_audit=_path(record, "unitization_audit_path"),
        original_review=_path(record, "original_review_path"),
        structural_flags=_path(record, "structural_flags_path"),
        structural_audit=_path(record, "structural_review_audit_path"),
        structural_card=_path(record, "structural_review_run_card_path"),
        structural_registry=_path(record, "structural_review_registry_path"),
        structural_model=_text(record, "structural_review_model_key"),
        merged_review=_path(record, "merged_review_path"),
    )


def _path(record: Mapping[str, object], field: str) -> Path:
    return Path(_text(record, field))


def _text(record: Mapping[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise StageAReplayExecutorError(f"{field} must be non-empty text")
    return value
