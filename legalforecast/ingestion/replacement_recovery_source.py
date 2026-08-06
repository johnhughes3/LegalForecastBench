"""Closed recovery-source descriptor derivation for replacement cohorts."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

SOURCE_RUN_CARD_SCHEMA = "legalforecast.replacement_recovery_source_run_card.v1"
RECOVERY_RUN_CARD_SCHEMA = "legalforecast.recap_fetch_quarantine_recovery_run_card.v2"
CLEARANCE_RUN_CARD_SCHEMAS = frozenset(
    {
        "legalforecast.provenance_quarantine_clearance_run_card.v1",
        "legalforecast.provenance_public_marker_clearance_run_card.v1",
    }
)
RESOLVED_RUN_CARD_SCHEMA = "legalforecast.acquisition_run_card.v1"
RECOVERY_STAGE = "recover-recap-fetch-quarantine"
CLEARANCE_STAGE = "finalize-provenance-quarantine"
INITIAL_KIND = "initial_v2"
SUCCESSOR_KIND = "successor"
RESOLVED_STAGE = "resolve-post-recovery-documents"

_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")


class ReplacementRecoverySourceError(ValueError):
    """Raised when an authenticated recovery source cannot be derived exactly."""


@dataclass(frozen=True, slots=True)
class RecoverySourceCoordinates:
    """Paths that a completed recovery card authoritatively selects."""

    kind: str
    selection_path: Path
    purchase_policy_path: Path
    cohort_policy_path: Path
    budget_plan_path: Path
    purchase_ledger_path: Path
    attempt_policy_path: Path
    replacement_authority_path: Path | None


@dataclass(frozen=True, slots=True)
class ResolvedSourceCoordinates:
    """Closed resolved-document output and its committed input paths."""

    resolved_path: Path
    resolved_sha256: str
    input_paths: tuple[Path, ...]
    input_sha256: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ClearanceSourceCoordinates:
    """Closed clearance output committed by its completed producer card."""

    clearance_path: Path
    clearance_sha256: str


def _string_mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ReplacementRecoverySourceError(f"{label} must be an object")
    untyped = cast(Mapping[object, object], value)
    if not all(isinstance(key, str) for key in untyped):
        raise ReplacementRecoverySourceError(f"{label} must be an object")
    return cast(Mapping[str, object], value)


def _path_sequence(
    value: object, *, label: str, allow_duplicates: bool = False
) -> tuple[Path, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ReplacementRecoverySourceError(f"{label} must be a path list")
    paths: list[Path] = []
    for raw_path in cast(Sequence[object], value):
        if not isinstance(raw_path, str) or not raw_path:
            raise ReplacementRecoverySourceError(f"{label} contains an invalid path")
        paths.append(Path(raw_path).absolute())
    if not allow_duplicates and len({path.resolve() for path in paths}) != len(paths):
        raise ReplacementRecoverySourceError(f"{label} repeats a path")
    return tuple(paths)


def _require_completed_provider_free_recovery(card: Mapping[str, object]) -> None:
    if (
        card.get("schema_version") != RECOVERY_RUN_CARD_SCHEMA
        or card.get("stage") != RECOVERY_STAGE
        or card.get("status") != "completed"
        or card.get("dry_run") is not False
        or card.get("execute") is not True
        or card.get("paid_activity_requested") is not False
        or card.get("paid_activity_executed") is not False
    ):
        raise ReplacementRecoverySourceError(
            "recovery source requires a completed provider-free recovery run card"
        )


def derive_recovery_source_coordinates(
    card: Mapping[str, object],
) -> RecoverySourceCoordinates:
    """Derive descriptor paths from one closed recovery run card."""

    _require_completed_provider_free_recovery(card)
    paths = _path_sequence(
        card.get("input_paths"),
        label="recovery input_paths",
        allow_duplicates=True,
    )
    mode = card.get("authority_mode")
    if mode == "initial_projection":
        if len(paths) not in {8, 10}:
            raise ReplacementRecoverySourceError("initial recovery input paths differ")
        if len({path.resolve() for path in paths}) != len(paths):
            raise ReplacementRecoverySourceError(
                "initial recovery input paths repeat a path"
            )
        kind = INITIAL_KIND
        selection_path = paths[0]
        purchase_policy_path = paths[3]
        cohort_policy_path = paths[4]
        budget_path = paths[5]
        ledger_path = paths[6]
        attempt_policy_path = paths[7]
        authority_path = None
        expected_commitments = {
            "selection",
            "case_relevance",
            "target_projection_run_card",
            "purchase_policy",
            "cohort_policy",
            "budget_plan",
            "attempt_policy",
        }
    elif mode == "replacement_successor":
        if len(paths) not in {8, 10}:
            raise ReplacementRecoverySourceError(
                "successor recovery input paths differ"
            )
        kind = SUCCESSOR_KIND
        selection_path = paths[0]
        if selection_path.resolve() != paths[1].resolve():
            raise ReplacementRecoverySourceError(
                "successor recovery selection and case relevance differ"
            )
        if len({path.resolve() for path in paths}) != len(paths) - 1:
            raise ReplacementRecoverySourceError(
                "successor recovery input paths repeat an unexpected path"
            )
        purchase_policy_path = paths[2]
        cohort_policy_path = paths[3]
        budget_path = paths[4]
        ledger_path = paths[5]
        attempt_policy_path = paths[6]
        authority_path = paths[7]
        expected_commitments = {
            "selection",
            "case_relevance",
            "purchase_policy",
            "cohort_policy",
            "budget_plan",
            "attempt_policy",
            "replacement_purchase_authority",
        }
    else:
        raise ReplacementRecoverySourceError(
            "recovery authority_mode is not initial_projection or replacement_successor"
        )
    if len(paths) == 10:
        expected_commitments |= {"courtlistener_fixture", "fixture_documents"}
    raw_commitments = _string_mapping(
        card.get("source_commitments"), label="recovery source commitments"
    )
    if set(raw_commitments) != expected_commitments:
        raise ReplacementRecoverySourceError(
            "recovery source commitments have extra or missing fields"
        )
    return RecoverySourceCoordinates(
        kind=kind,
        selection_path=selection_path,
        purchase_policy_path=purchase_policy_path,
        cohort_policy_path=cohort_policy_path,
        budget_plan_path=budget_path,
        purchase_ledger_path=ledger_path,
        attempt_policy_path=attempt_policy_path,
        replacement_authority_path=authority_path,
    )


def _path_commitment(
    value: object,
    *,
    label: str,
) -> tuple[Path, str]:
    record = _string_mapping(value, label=f"{label} commitment")
    if set(record) != {"path", "sha256"}:
        raise ReplacementRecoverySourceError(f"{label} commitment fields differ")
    raw_path = record.get("path")
    raw_sha256 = record.get("sha256")
    if not isinstance(raw_path, str) or not raw_path:
        raise ReplacementRecoverySourceError(f"{label} commitment path is invalid")
    if not isinstance(raw_sha256, str) or _SHA256.fullmatch(raw_sha256) is None:
        raise ReplacementRecoverySourceError(f"{label} commitment SHA-256 is invalid")
    return Path(raw_path).absolute(), raw_sha256


def derive_clearance_source_coordinates(
    card: Mapping[str, object],
) -> ClearanceSourceCoordinates:
    """Derive and close the clearance output selected by its producer card."""

    schema_version = card.get("schema_version")
    if (
        not isinstance(schema_version, str)
        or schema_version not in CLEARANCE_RUN_CARD_SCHEMAS
        or card.get("stage") != CLEARANCE_STAGE
        or card.get("status") != "completed"
        or card.get("dry_run") is not False
        or card.get("execute") is not True
        or card.get("provider_activity_requested") is not False
        or card.get("provider_activity_executed") is not False
        or card.get("human_review_requested") is not False
        or card.get("human_review_executed") is not False
        or card.get("paid_activity_requested") is not False
        or card.get("paid_activity_executed") is not False
    ):
        raise ReplacementRecoverySourceError(
            "clearance source requires a completed provider-free clearance run card"
        )
    commitments = _string_mapping(
        card.get("output_commitments"), label="clearance output commitments"
    )
    if set(commitments) != {"disclosure_clearance", "disclosure_quarantine"}:
        raise ReplacementRecoverySourceError(
            "clearance output commitments have extra or missing fields"
        )
    clearance_path, clearance_sha256 = _path_commitment(
        commitments.get("disclosure_clearance"),
        label="disclosure clearance",
    )
    quarantine_path, _quarantine_sha256 = _path_commitment(
        commitments.get("disclosure_quarantine"),
        label="disclosure quarantine",
    )
    raw_outputs = card.get("output_paths")
    outputs = _path_sequence(raw_outputs, label="clearance output_paths")
    if {path.resolve() for path in outputs} != {
        clearance_path.resolve(),
        quarantine_path.resolve(),
    }:
        raise ReplacementRecoverySourceError("clearance output paths rebound")
    return ClearanceSourceCoordinates(
        clearance_path=clearance_path,
        clearance_sha256=clearance_sha256,
    )


def derive_resolved_source_coordinates(
    card: Mapping[str, object],
    *,
    expected_input_paths: Sequence[Path],
    expected_ledger_path: Path,
    expected_purchase_state_sha256: str,
) -> ResolvedSourceCoordinates:
    """Authenticate the closed path projection of a resolve-stage run card."""

    if (
        card.get("schema_version") != RESOLVED_RUN_CARD_SCHEMA
        or card.get("stage") != RESOLVED_STAGE
        or card.get("status") != "completed"
        or card.get("dry_run") is not False
        or card.get("execute") is not True
        or card.get("paid_activity_requested") is not False
        or card.get("paid_activity_executed") is not False
    ):
        raise ReplacementRecoverySourceError(
            "resolved source requires a completed provider-free resolve run card"
        )
    inputs = _path_sequence(card.get("input_paths"), label="resolved input_paths")
    expected = {path.resolve() for path in expected_input_paths}
    if not expected <= {path.resolve() for path in inputs}:
        raise ReplacementRecoverySourceError(
            "resolved source omits authenticated recovery inputs"
        )
    raw_sources = _string_mapping(
        card.get("source_commitments"), label="resolved source commitments"
    )
    expected_source_names = {f"input_{index:02d}" for index in range(len(inputs))}
    if set(raw_sources) != expected_source_names:
        raise ReplacementRecoverySourceError(
            "resolved source commitments have extra or missing fields"
        )
    source_digests: list[str] = []
    for index, input_path in enumerate(inputs):
        committed_path, digest = _path_commitment(
            raw_sources[f"input_{index:02d}"],
            label=f"resolved input_{index:02d}",
        )
        if committed_path.resolve() != input_path.resolve():
            raise ReplacementRecoverySourceError(
                "resolved source commitment path rebound"
            )
        source_digests.append(digest)
    raw_outputs = card.get("output_paths")
    outputs = _path_sequence(raw_outputs, label="resolved output_paths")
    if len(outputs) != 2 or outputs[1].resolve() != expected_ledger_path.resolve():
        raise ReplacementRecoverySourceError(
            "resolved post-recovery output paths differ"
        )
    raw_output_commitments = _string_mapping(
        card.get("output_commitments"),
        label="resolved post-recovery output commitments",
    )
    if set(raw_output_commitments) != {
        "resolved_post_recovery_documents",
        "purchase_state_sha256",
    }:
        raise ReplacementRecoverySourceError(
            "resolved post-recovery output commitments differ"
        )
    resolved_path, resolved_sha256 = _path_commitment(
        raw_output_commitments["resolved_post_recovery_documents"],
        label="resolved post-recovery documents",
    )
    if resolved_path.resolve() != outputs[0].resolve():
        raise ReplacementRecoverySourceError(
            "resolved post-recovery output path rebound"
        )
    if (
        raw_output_commitments.get("purchase_state_sha256")
        != expected_purchase_state_sha256
        or card.get("purchase_state_after_sha256") != expected_purchase_state_sha256
    ):
        raise ReplacementRecoverySourceError(
            "resolved post-recovery purchase state changed"
        )
    return ResolvedSourceCoordinates(
        resolved_path=resolved_path,
        resolved_sha256=resolved_sha256,
        input_paths=inputs,
        input_sha256=tuple(source_digests),
    )


def validate_source_ordinal(*, kind: str, ordinal: int) -> None:
    """Require the index's single-initial then positive-successor ordering."""

    if isinstance(ordinal, bool) or ordinal < 0:
        raise ReplacementRecoverySourceError(
            "replacement recovery source ordinal must be a nonnegative integer"
        )
    if kind == INITIAL_KIND and ordinal != 0:
        raise ReplacementRecoverySourceError("initial_v2 source requires ordinal 0")
    if kind == SUCCESSOR_KIND and ordinal == 0:
        raise ReplacementRecoverySourceError(
            "successor source requires a positive ordinal"
        )


def build_recovery_source_descriptor(
    *,
    coordinates: RecoverySourceCoordinates,
    ordinal: int,
    recovery_root: Path,
    purchased_clearance_path: Path,
    purchased_clearance_run_card_path: Path,
    resolved_post_recovery_documents_path: Path | None,
    replacement_controlled_private_root: Path | None,
) -> dict[str, object]:
    """Build the exact descriptor schema after callers authenticate every path."""

    validate_source_ordinal(kind=coordinates.kind, ordinal=ordinal)
    common: dict[str, object] = {
        "kind": coordinates.kind,
        "ordinal": ordinal,
        "recovery_root": str(recovery_root.absolute()),
        "selection": str(coordinates.selection_path.absolute()),
        "purchased_clearance": str(purchased_clearance_path.absolute()),
        "purchased_clearance_run_card": str(
            purchased_clearance_run_card_path.absolute()
        ),
        "resolved_post_recovery_documents": (
            str(resolved_post_recovery_documents_path.absolute())
            if resolved_post_recovery_documents_path is not None
            else None
        ),
    }
    if coordinates.kind == INITIAL_KIND:
        if (
            coordinates.replacement_authority_path is not None
            or replacement_controlled_private_root is not None
        ):
            raise ReplacementRecoverySourceError(
                "initial_v2 source cannot carry successor authority"
            )
        return common
    if (
        coordinates.replacement_authority_path is None
        or replacement_controlled_private_root is None
    ):
        raise ReplacementRecoverySourceError(
            "successor source requires replacement controlled private root"
        )
    return {
        **common,
        "replacement_purchase_authority": str(
            coordinates.replacement_authority_path.absolute()
        ),
        "replacement_controlled_private_root": str(
            replacement_controlled_private_root.absolute()
        ),
        "replacement_budget_plan": str(coordinates.budget_plan_path.absolute()),
    }
