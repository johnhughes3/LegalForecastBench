"""Discover a real recovery-slice preflight manifest without granting authority.

The lineage index is deliberately only a locator.  This module authenticates the
selected stage-head chain again, then follows the authenticated materialization
card to the recovery-consolidation card and its native predecessor cards.  It
does not contact a provider, mutate a Cycle 1 artifact, or turn an incomplete
historical record into a passing preflight manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from legalforecast.contracts.schemas import (
    CYCLE_PREFLIGHT_MANIFEST_SIDECAR_V1,
    CYCLE_PREFLIGHT_REPORT_V2,
)
from legalforecast.ingestion.canonical_json import (
    canonical_json_bytes,
    canonical_json_value_bytes,
)
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseSnapshot,
    read_case_dev_purchase_snapshot,
    verify_case_dev_purchase_policy,
)
from legalforecast.ingestion.cycle_lineage_index import (
    INDEX_ENVIRONMENT_VARIABLE,
    CycleLineageIndexError,
    _authenticate_stage_head_entry,  # pyright: ignore[reportPrivateUsage]
    _load_index,  # pyright: ignore[reportPrivateUsage]
    locate_cycle_lineage,
)
from legalforecast.ingestion.disclosure_review_bundle import (
    ReviewBundleError,
    read_unique_regular_file,
)
from legalforecast.ingestion.replacement_recovery_source import (
    SOURCE_RUN_CARD_SCHEMA,
    SOURCE_RUN_CARD_SCHEMA_V2,
)
from legalforecast.ingestion.resolved_post_recovery import (
    ResolvedPostRecoveryError,
    reconstruct_pre_resolution_purchase_snapshot,
)

SIDECAR_SCHEMA = CYCLE_PREFLIGHT_MANIFEST_SIDECAR_V1.value
_SHA256_PREFIX = "sha256:"
_REQUIRED_NATIVE_STAGES = frozenset(
    {
        "recover-recap-fetch-quarantine",
        "finalize-provenance-quarantine",
        "resolve-post-recovery-documents",
        "build-replacement-recovery-source",
    }
)


class CyclePreflightManifestError(ValueError):
    """Raised when native authenticated evidence cannot yield one manifest."""


@dataclass(frozen=True, slots=True)
class NativeRecoverySlice:
    """Authenticated native card paths for one recovery vertical slice."""

    cycle_id: str
    lineage_root_identity_sha256: str
    materialize_card: Path
    consolidation_card: Path
    recovery_card: Path
    clearance_card: Path
    resolution_card: Path
    replacement_source_card: Path


@dataclass(frozen=True, slots=True)
class HistoricalPurchaseSnapshots:
    """Logically authenticated purchase states recovered from resolver evidence."""

    before_recovery: CaseDevPurchaseSnapshot
    after_recovery: CaseDevPurchaseSnapshot
    current: CaseDevPurchaseSnapshot
    prior_resolution_card: Path


def verify_v2_sidecar(
    path: Path, *, trusted_index_path: Path | None = None
) -> dict[str, object]:
    """Verify the additive, real two-transition recovery graph from a sidecar.

    v1 intentionally models one purchase transition.  This read-only v2 report
    instead proves the two native transitions independently and keeps their
    distinct after-states explicit.
    """

    sidecar = _read_json(path, label="v2 discovery sidecar")
    if (
        sidecar.get("schema_version") != SIDECAR_SCHEMA
        or sidecar.get("non_authoritative") is not True
    ):
        raise CyclePreflightManifestError(
            "v2 verification requires a discovery sidecar"
        )
    cards = _object(sidecar.get("native_cards"), label="v2 native cards")
    sidecar_index = Path(_text(sidecar.get("index_path"), label="v2 index path"))
    index_path = _trusted_index_path(trusted_index_path)
    if sidecar_index.absolute() != index_path:
        raise CyclePreflightManifestError(
            "v2 sidecar does not match trusted lineage index"
        )
    slice_ = NativeRecoverySlice(
        cycle_id=_text(sidecar.get("cycle_id"), label="v2 cycle id"),
        lineage_root_identity_sha256=_text(
            sidecar.get("lineage_root_identity_sha256"), label="v2 root identity"
        ),
        materialize_card=Path(
            _text(cards.get("materialize"), label="v2 materialize card")
        ),
        consolidation_card=Path(
            _text(cards.get("consolidation"), label="v2 consolidation card")
        ),
        recovery_card=Path(_text(cards.get("recovery"), label="v2 recovery card")),
        clearance_card=Path(_text(cards.get("clearance"), label="v2 clearance card")),
        resolution_card=Path(
            _text(cards.get("resolution"), label="v2 resolution card")
        ),
        replacement_source_card=Path(
            _text(cards.get("replacement_source"), label="v2 source card")
        ),
    )
    # The sidecar is only a locator.  Re-run the authenticated active-chain
    # traversal and require every identity it carries to match exactly.
    observed = discover_native_recovery_slice(
        index_path=index_path, cycle_id=slice_.cycle_id
    )
    if observed != slice_:
        raise CyclePreflightManifestError("v2 sidecar differs from active lineage")
    report = _verify_v2_slice(slice_)
    # The cards and advisory locator can change between discovery and the final
    # read.  Reauthenticate the whole selection immediately before acceptance;
    # do not let a time-of-check snapshot authorize a later set of bytes.
    if (
        discover_native_recovery_slice(index_path=index_path, cycle_id=slice_.cycle_id)
        != slice_
    ):
        raise CyclePreflightManifestError("v2 lineage changed during verification")
    # A path-only rediscovery cannot catch byte changes under stable coordinates.
    # Repeat the complete semantic pass after the final active-chain check.
    if _verify_v2_slice(slice_) != report:
        raise CyclePreflightManifestError("v2 lineage changed during verification")
    return report


def _verify_v2_slice(slice_: NativeRecoverySlice) -> dict[str, object]:
    """Authenticate both native recovery transitions and their source closure."""

    recovery = _read_json(slice_.recovery_card, label="v2 recovery card")
    _verify_card_semantics(slice_.recovery_card, recovery, label="v2 recovery card")
    recovery_inputs = _committed_paths(recovery, label="v2 recovery card")
    policy_path = _one(
        [path for path in recovery_inputs if path.name == "purchase-policy-v2.json"],
        label="v2 purchase policy",
    )
    ledger_path = _one(
        [
            path
            for path in _paths(
                _read_json(slice_.resolution_card, label="v2 resolution card"),
                field="input_paths",
                label="v2 resolution card",
            )
            if path.suffix == ".sqlite3"
        ],
        label="v2 purchase ledger",
    )
    snapshots = reconstruct_historical_purchase_snapshots(
        slice_,
        ledger_path=ledger_path,
        policy_path=policy_path,
        initialization_receipt_path=ledger_path.parent
        / "purchase-ledger-initialization.json",
    )
    if (
        snapshots.before_recovery.purchase_state_sha256
        == snapshots.after_recovery.purchase_state_sha256
        or snapshots.after_recovery.purchase_state_sha256
        == snapshots.current.purchase_state_sha256
    ):
        raise CyclePreflightManifestError("v2 purchase transitions are not distinct")
    materialize = _read_json(slice_.materialize_card, label="v2 materialize card")
    materialize_commitments = _committed_paths(materialize, label="v2 materialize card")
    consolidation = _require_committed_card(
        slice_.consolidation_card,
        commitments=materialize_commitments,
        label="v2 consolidation card",
    )
    consolidation_commitments = _committed_paths(
        consolidation, label="v2 consolidation card"
    )
    _index_path, index_card = _one(
        [
            (candidate, card)
            for candidate, card in _committed_cards(
                consolidation_commitments, label="v2 consolidation input"
            )
            if _stage(card) == "build-replacement-recovery-index"
        ],
        label="v2 recovery index card",
    )
    index_commitments = _committed_paths(index_card, label="v2 recovery index card")
    descriptors = [
        path
        for path in index_commitments
        if path.name in {"0000-initial-v2.json", "0001-successor.json"}
    ]
    if len(descriptors) != 2:
        raise CyclePreflightManifestError(
            "v2 source closure lacks both ordinal descriptors"
        )
    producers: dict[int, tuple[Path, Mapping[str, object]]] = {}
    descriptor_records: dict[int, Mapping[str, object]] = {}
    for descriptor in descriptors:
        descriptor_record = _require_committed_card(
            descriptor, commitments=index_commitments, label="v2 descriptor"
        )
        _validate_descriptor(descriptor_record)
        producer, producer_card = _producer_for_descriptor(
            descriptor, index_commitments=index_commitments
        )
        _verify_card_inputs(producer_card, label="v2 producer card")
        _verify_card_outputs(producer, producer_card, label="v2 producer card")
        if descriptor_record.get("ordinal") != producer_card.get("ordinal"):
            raise CyclePreflightManifestError(
                "v2 producer ordinal differs from descriptor"
            )
        ordinal = descriptor_record.get("ordinal")
        if not isinstance(ordinal, int) or ordinal not in {0, 1}:
            raise CyclePreflightManifestError("v2 descriptor ordinal is invalid")
        producers[ordinal] = (producer, producer_card)
        descriptor_records[ordinal] = descriptor_record
    if set(producers) != {0, 1}:
        raise CyclePreflightManifestError("v2 source closure lacks both producers")

    terminal_recovery, terminal_clearance, terminal_resolution = _terminal_cards(
        producers[0][1], descriptor_records[0]
    )
    _verify_terminal_resolution_transition(
        terminal_resolution, historical_resolution=snapshots.prior_resolution_card
    )
    for card_path, card, label in (
        (
            terminal_recovery,
            _read_json(terminal_recovery, label="terminal recovery"),
            "terminal recovery",
        ),
        (
            terminal_clearance,
            _read_json(terminal_clearance, label="terminal clearance"),
            "terminal clearance",
        ),
        (
            slice_.clearance_card,
            _read_json(slice_.clearance_card, label="successor clearance"),
            "successor clearance",
        ),
    ):
        _verify_card_semantics(card_path, card, label=label)
    terminal_resolution_card = _read_json(
        terminal_resolution, label="terminal resolution"
    )
    _verify_resolution_card(
        terminal_resolution_card,
        ledger_path=ledger_path,
        label="terminal resolution",
    )
    # Resolver cards name a mutable SQLite implementation state.  Their logical
    # histories are authenticated by ``reconstruct_historical_purchase_snapshots``
    # above; treating the current database bytes as immutable would make a valid
    # replay falsely fail.  The selected resolution itself is still required to
    # be committed by the source closure in that reconstruction.
    return {
        "schema_version": CYCLE_PREFLIGHT_REPORT_V2.value,
        "ok": True,
        "nodes": [
            {
                "id": "successor-recovery",
                "status": "PASSED",
                "depends_on": [],
            },
            {
                "id": "successor-clearance-resolution",
                "status": "PASSED",
                "depends_on": ["successor-recovery"],
                "after": snapshots.after_recovery.purchase_state_sha256,
            },
            {
                "id": "terminal-recovery",
                "status": "PASSED",
                "depends_on": [],
            },
            {
                "id": "terminal-clearance",
                "status": "PASSED",
                "depends_on": ["terminal-recovery"],
            },
            {
                "id": "terminal-resolution",
                "status": "PASSED",
                "depends_on": ["terminal-clearance"],
                "after": snapshots.current.purchase_state_sha256,
            },
            {
                "id": "replacement-source-closure",
                "status": "PASSED",
                "depends_on": [
                    "successor-clearance-resolution",
                    "terminal-resolution",
                ],
                "descriptors": 2,
            },
        ],
    }


def _read_json(path: Path, *, label: str) -> Mapping[str, object]:
    try:
        raw = json.loads(read_unique_regular_file(path))
    except (OSError, ReviewBundleError, UnicodeError, json.JSONDecodeError) as exc:
        raise CyclePreflightManifestError(f"{label} is unavailable or invalid") from exc
    if not isinstance(raw, Mapping):
        raise CyclePreflightManifestError(f"{label} must be a JSON object")
    return cast(Mapping[str, object], raw)


def _text(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise CyclePreflightManifestError(f"{label} must be non-empty text")
    return value


def _object(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(
        isinstance(key, str) for key in cast(Mapping[object, object], value)
    ):
        raise CyclePreflightManifestError(f"{label} must be a JSON object")
    return cast(Mapping[str, object], value)


def _trusted_index_path(configured_path: Path | None = None) -> Path:
    """Return the operator-selected index; a diagnostic sidecar never selects it."""

    configured = (
        str(configured_path)
        if configured_path is not None
        else os.environ.get(INDEX_ENVIRONMENT_VARIABLE)
    )
    if not configured:
        raise CyclePreflightManifestError(
            f"{INDEX_ENVIRONMENT_VARIABLE} is required to verify a v2 sidecar"
        )
    path = Path(configured).absolute()
    if path.is_symlink() or not path.is_file():
        raise CyclePreflightManifestError(
            "trusted lineage index is unavailable or unsafe"
        )
    return path


def _paths(card: Mapping[str, object], *, field: str, label: str) -> tuple[Path, ...]:
    raw = card.get(field)
    if not isinstance(raw, list):
        raise CyclePreflightManifestError(f"{label} lacks {field}")
    paths: list[Path] = []
    for value in cast(list[object], raw):
        path = Path(_text(value, label=f"{label} {field}"))
        if not path.is_absolute() or path != Path(os.path.abspath(path)):
            raise CyclePreflightManifestError(f"{label} {field} must be absolute")
        paths.append(path)
    return tuple(paths)


def _committed_paths(card: Mapping[str, object], *, label: str) -> dict[Path, str]:
    raw = card.get("source_commitments")
    if not isinstance(raw, Mapping):
        raise CyclePreflightManifestError(f"{label} lacks source commitments")
    committed: dict[Path, str] = {}
    for key, value in cast(Mapping[object, object], raw).items():
        if isinstance(key, str) and key.startswith("/") and isinstance(value, str):
            path, digest = Path(key), value
        elif isinstance(value, Mapping):
            record = cast(Mapping[object, object], value)
            raw_path, raw_digest = record.get("path"), record.get("sha256")
            if not isinstance(raw_path, str) or not isinstance(raw_digest, str):
                continue
            path, digest = Path(raw_path), raw_digest
        else:
            continue
        if (
            not path.is_absolute()
            or path != Path(os.path.abspath(path))
            or not digest.startswith(_SHA256_PREFIX)
            or len(digest) != len(_SHA256_PREFIX) + 64
        ):
            raise CyclePreflightManifestError(f"{label} has an invalid commitment")
        committed[path] = digest
    return committed


def _require_committed_card(
    path: Path, *, commitments: Mapping[Path, str], label: str
) -> Mapping[str, object]:
    expected = commitments.get(path)
    if expected is None:
        raise CyclePreflightManifestError(f"{label} is not committed by its parent")
    try:
        payload = read_unique_regular_file(path)
    except (OSError, ReviewBundleError) as exc:
        raise CyclePreflightManifestError(f"{label} is unavailable or unsafe") from exc
    if hashlib.sha256(payload).hexdigest() != expected.removeprefix(_SHA256_PREFIX):
        raise CyclePreflightManifestError(
            f"{label} bytes differ from parent commitment"
        )
    try:
        raw = json.loads(payload)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CyclePreflightManifestError(f"{label} is not JSON") from exc
    if not isinstance(raw, Mapping):
        raise CyclePreflightManifestError(f"{label} must be a JSON object")
    return cast(Mapping[str, object], raw)


def _one[T](items: Sequence[T], *, label: str) -> T:
    if len(items) != 1:
        raise CyclePreflightManifestError(f"{label} is ambiguous ({len(items)} found)")
    return items[0]


def _committed_cards(
    commitments: Mapping[Path, str], *, label: str
) -> tuple[tuple[Path, Mapping[str, object]], ...]:
    """Return only committed JSON cards; ordinary committed inputs are not cards."""

    cards: list[tuple[Path, Mapping[str, object]]] = []
    for path in commitments:
        try:
            card = _require_committed_card(path, commitments=commitments, label=label)
        except CyclePreflightManifestError:
            continue
        if _stage(card) is not None:
            cards.append((path, card))
    return tuple(cards)


def _stage(card: Mapping[str, object]) -> str | None:
    value = card.get("stage")
    return value if isinstance(value, str) else None


def _active_head_chain(
    index_path: Path, cycle_id: str
) -> tuple[dict[str, object], ...]:
    """Reauthenticate every indexed head in the selected active predecessor chain."""

    try:
        _status = locate_cycle_lineage(index_path=index_path, cycle_id=cycle_id)
        entries, heads = _load_index(index_path, missing_ok=False)
    except CycleLineageIndexError as exc:
        raise CyclePreflightManifestError(str(exc)) from exc
    candidates = [head for head in heads if head["cycle_id"] == cycle_id]
    superseded = {
        cast(str, head["supersedes_root_identity_sha256"])
        for head in candidates
        if head["supersedes_root_identity_sha256"] is not None
    }
    active = [
        head for head in candidates if head["root_identity_sha256"] not in superseded
    ]
    if len(active) != 1:
        raise CyclePreflightManifestError("active stage head is ambiguous")
    by_root = {
        cast(str, item["root_identity_sha256"]): item for item in [*entries, *heads]
    }
    chain: list[dict[str, object]] = []
    cursor: Mapping[str, object] | None = active[0]
    while cursor is not None:
        if "command" not in cursor:
            raise CyclePreflightManifestError(
                "active stage chain reaches a non-stage root"
            )
        head = dict(cursor)
        try:
            _authenticate_stage_head_entry(head)
        except CycleLineageIndexError as exc:
            raise CyclePreflightManifestError(str(exc)) from exc
        chain.append(head)
        predecessor = head["supersedes_root_identity_sha256"]
        cursor = None if predecessor is None else by_root.get(cast(str, predecessor))
    return tuple(chain)


def discover_native_recovery_slice(
    *, index_path: Path, cycle_id: str | None = None
) -> NativeRecoverySlice:
    """Discover the one fully committed native recovery slice from local state."""

    try:
        status = locate_cycle_lineage(index_path=index_path, cycle_id=cycle_id)
    except CycleLineageIndexError as exc:
        raise CyclePreflightManifestError(str(exc)) from exc
    resolved_cycle_id = _text(status.get("cycle_id"), label="lineage cycle id")
    chain = _active_head_chain(index_path, resolved_cycle_id)
    materialize_head = _one(
        [head for head in chain if head["stage"] == "materialize-cohort-documents"],
        label="materialize stage head",
    )
    materialize = Path(
        _text(materialize_head["run_card_path"], label="materialize path")
    )
    expected_materialize = _text(
        materialize_head.get("run_card_sha256"), label="materialize active-head digest"
    )
    if len(expected_materialize) != 64 or any(
        character not in "0123456789abcdef" for character in expected_materialize
    ):
        raise CyclePreflightManifestError("materialize active-head digest is invalid")
    try:
        materialize_bytes = read_unique_regular_file(materialize)
    except (OSError, ReviewBundleError) as exc:
        raise CyclePreflightManifestError(
            "materialize active-head card is unavailable"
        ) from exc
    if hashlib.sha256(materialize_bytes).hexdigest() != expected_materialize:
        raise CyclePreflightManifestError(
            "materialize card differs from active-head commitment"
        )
    try:
        materialize_record = json.loads(materialize_bytes)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CyclePreflightManifestError(
            "materialize active-head card is not JSON"
        ) from exc
    if not isinstance(materialize_record, Mapping):
        raise CyclePreflightManifestError(
            "materialize active-head card is not an object"
        )
    materialize_card = cast(Mapping[str, object], materialize_record)
    materialize_commitments = _committed_paths(
        materialize_card, label="materialize run card"
    )
    consolidation = _one(
        [
            path
            for path, card in _committed_cards(
                materialize_commitments, label="materialize input"
            )
            if _stage(card) == "consolidate-replacement-recovery"
        ],
        label="committed consolidation card",
    )
    consolidation_card = _require_committed_card(
        consolidation, commitments=materialize_commitments, label="consolidation card"
    )
    commitments = _committed_paths(consolidation_card, label="consolidation card")
    cards: dict[str, list[Path]] = {stage: [] for stage in _REQUIRED_NATIVE_STAGES}
    for path, card in _committed_cards(commitments, label="consolidation input"):
        stage = _stage(card)
        if stage in cards:
            cards[stage].append(path)
    # A resolver consumes the recovery *artifacts*, not necessarily the recovery
    # card itself.  The successor descriptor is the authenticated relationship
    # that binds this recovery root, clearance card, and resolved output.  Do
    # not invent a direct-card edge that the native run card never promised.
    triples = [
        (recovery, clearance, resolution)
        for recovery in cards["recover-recap-fetch-quarantine"]
        for clearance in cards["finalize-provenance-quarantine"]
        for resolution in cards["resolve-post-recovery-documents"]
    ]
    index_cards = [
        (path, card)
        for path, card in _committed_cards(commitments, label="consolidation input")
        if _stage(card) == "build-replacement-recovery-index"
    ]
    _index_path, index_card = _one(index_cards, label="recovery index card")
    index_commitments = _committed_paths(index_card, label="recovery index card")
    resolved_triples: list[tuple[Path, Path, Path, Path]] = []
    for recovery, clearance, resolution in triples:
        descriptors = [
            path
            for path in index_commitments
            if _descriptor_matches(
                _require_committed_card(
                    path, commitments=index_commitments, label="recovery descriptor"
                ),
                recovery=recovery,
                clearance=clearance,
                resolution=resolution,
            )
        ]
        for descriptor in descriptors:
            try:
                source = _source_card_for_descriptor(
                    descriptor,
                    recovery=recovery,
                    clearance=clearance,
                    resolution=resolution,
                )
            except CyclePreflightManifestError:
                continue
            resolved_triples.append((recovery, clearance, resolution, source))
    recovery, clearance, resolution, source = _one(
        resolved_triples, label="recovery/clearance/resolution/source path"
    )
    return NativeRecoverySlice(
        cycle_id=resolved_cycle_id,
        lineage_root_identity_sha256=_text(
            status.get("root_identity_sha256"), label="lineage root identity"
        ),
        materialize_card=materialize,
        consolidation_card=consolidation,
        recovery_card=recovery,
        clearance_card=clearance,
        resolution_card=resolution,
        replacement_source_card=source,
    )


def _descriptor_matches(
    descriptor: Mapping[str, object],
    *,
    recovery: Path,
    clearance: Path,
    resolution: Path,
) -> bool:
    return (
        descriptor.get("kind") == "successor"
        and descriptor.get("ordinal") == 1
        and descriptor.get("recovery_root") == str(recovery.parent.parent)
        and descriptor.get("purchased_clearance_run_card") == str(clearance)
        and descriptor.get("resolved_post_recovery_documents")
        == str(resolution.parent.parent / "resolved-post-recovery-documents.jsonl")
    )


def _source_card_for_descriptor(
    descriptor: Path,
    *,
    recovery: Path,
    clearance: Path,
    resolution: Path,
) -> Path:
    cards_dir = descriptor.parent / "run-cards"
    try:
        candidates = tuple(sorted(cards_dir.glob("*.json")))
    except OSError as exc:
        raise CyclePreflightManifestError(
            "replacement source card directory is unavailable"
        ) from exc
    matches: list[Path] = []
    for candidate in candidates:
        if candidate.is_symlink():
            continue
        try:
            card = _read_json(candidate, label="replacement source card")
            outputs = _committed_paths(
                {"source_commitments": card.get("output_commitments")},
                label="replacement source card",
            )
            inputs = set(
                _paths(card, field="input_paths", label="replacement source card")
            )
        except CyclePreflightManifestError:
            continue
        if (
            _stage(card) == "build-replacement-recovery-source"
            and descriptor in outputs
            and {recovery, clearance, resolution} <= inputs
        ):
            try:
                payload = read_unique_regular_file(descriptor)
            except (OSError, ReviewBundleError) as exc:
                raise CyclePreflightManifestError(
                    "recovery descriptor is unavailable"
                ) from exc
            if hashlib.sha256(payload).hexdigest() == outputs[descriptor].removeprefix(
                _SHA256_PREFIX
            ):
                matches.append(candidate)
    return _one(matches, label="replacement source card")


def _producer_for_descriptor(
    descriptor: Path, *, index_commitments: Mapping[Path, str]
) -> tuple[Path, Mapping[str, object]]:
    """Return the one source producer which commits ``descriptor`` as output."""

    descriptor_card = _require_committed_card(
        descriptor, commitments=index_commitments, label="v2 descriptor"
    )
    ordinal = descriptor_card.get("ordinal")
    if not isinstance(ordinal, int) or ordinal not in {0, 1}:
        raise CyclePreflightManifestError("v2 descriptor ordinal is invalid")
    # The index commits the descriptor, and the descriptor has exactly one
    # canonical producer location.  Do not glob arbitrary, self-authored cards.
    candidate = (
        descriptor.parent
        / "run-cards"
        / (f"build-replacement-recovery-source-{ordinal:04}.json")
    )
    card = _read_json(candidate, label="v2 producer card")
    _validate_producer_card(card, descriptor, descriptor_card)
    outputs = _committed_paths(
        {"source_commitments": card.get("output_commitments")},
        label="v2 producer outputs",
    )
    if set(outputs) != {descriptor}:
        raise CyclePreflightManifestError("v2 producer output closure is malformed")
    _verify_path(descriptor, outputs[descriptor], label="v2 descriptor output")
    return candidate, card


def _validate_producer_card(
    card: Mapping[str, object],
    descriptor: Path,
    descriptor_card: Mapping[str, object],
) -> None:
    """Bind a source producer to the committed descriptor and its full witness set."""

    ordinal = descriptor_card["ordinal"]
    assert isinstance(ordinal, int)
    expected_schema = (
        SOURCE_RUN_CARD_SCHEMA_V2 if ordinal == 0 else SOURCE_RUN_CARD_SCHEMA
    )
    required = {
        "dry_run",
        "execute",
        "input_paths",
        "kind",
        "ordinal",
        "output_commitments",
        "output_paths",
        "paid_activity_executed",
        "paid_activity_requested",
        "provider_activity_executed",
        "provider_activity_requested",
        "purchase_state_sha256",
        "record_count",
        "schema_version",
        "source_commitments",
        "stage",
        "status",
    }
    # The initial-v2 bridge card records a replayed state.  The successor v1
    # card predates that field and its committed historical closure is instead
    # checked by the resolver replay below.
    if ordinal == 0:
        required.add("replayed_purchase_state_sha256")
    if (
        set(card) != required
        or card.get("schema_version") != expected_schema
        or card.get("stage") != "build-replacement-recovery-source"
        or card.get("status") != "completed"
        or card.get("kind") != descriptor_card.get("kind")
        or card.get("ordinal") != ordinal
        or card.get("record_count") != 1
        or card.get("dry_run") is not False
        or card.get("execute") is not True
        or any(
            card.get(field) is not False
            for field in (
                "paid_activity_executed",
                "paid_activity_requested",
                "provider_activity_executed",
                "provider_activity_requested",
            )
        )
    ):
        raise CyclePreflightManifestError(
            "v2 producer card is not an authenticated closure"
        )
    inputs = set(_paths(card, field="input_paths", label="v2 producer card"))
    commitments = _committed_paths(card, label="v2 producer card")
    if not inputs or inputs != set(commitments):
        raise CyclePreflightManifestError("v2 producer input closure is incomplete")
    outputs = _paths(card, field="output_paths", label="v2 producer card")
    if outputs != (descriptor,):
        raise CyclePreflightManifestError("v2 producer does not bind its descriptor")
    required_inputs = {
        Path(
            _text(
                descriptor_card.get("purchased_clearance_run_card"),
                label="descriptor clearance",
            )
        ),
        Path(
            _text(
                descriptor_card.get("resolved_post_recovery_documents"),
                label="descriptor resolution",
            )
        ),
        Path(_text(descriptor_card.get("selection"), label="descriptor selection")),
    }
    if not required_inputs <= inputs:
        raise CyclePreflightManifestError("v2 producer lacks descriptor witness inputs")


def _verify_path(path: Path, digest: str, *, label: str) -> None:
    """Check one regular-file SHA-256 commitment without following unsafe links."""

    if not digest.startswith(_SHA256_PREFIX) or len(digest) != len(_SHA256_PREFIX) + 64:
        raise CyclePreflightManifestError(f"{label} has an invalid commitment")
    try:
        payload = read_unique_regular_file(path)
    except (OSError, ReviewBundleError) as exc:
        raise CyclePreflightManifestError(f"{label} is unavailable or unsafe") from exc
    if hashlib.sha256(payload).hexdigest() != digest.removeprefix(_SHA256_PREFIX):
        raise CyclePreflightManifestError(f"{label} bytes differ from commitment")


def _verify_card_inputs(
    card: Mapping[str, object],
    *,
    label: str,
    mutable_paths: frozenset[Path] = frozenset(),
) -> None:
    """Authenticate every file for which a run card actually made a commitment."""

    commitments = _committed_paths(card, label=label)
    raw = _object(card.get("source_commitments"), label=f"{label} source commitments")
    for key, value in raw.items():
        if key.startswith("/"):
            if not isinstance(value, str):
                raise CyclePreflightManifestError(
                    f"{label} has a malformed source commitment"
                )
            continue
        record = _object(value, label=f"{label} source commitment")
        if set(record) == {"path", "sha256"}:
            _text(record["path"], label=f"{label} source commitment path")
            _text(record["sha256"], label=f"{label} source commitment digest")
            continue
        if set(record) != {"path", "document_count", "tree_sha256"}:
            raise CyclePreflightManifestError(
                f"{label} has a malformed source commitment"
            )
        tree_path = Path(_text(record["path"], label=f"{label} source commitment path"))
        if not isinstance(record["document_count"], int):
            raise CyclePreflightManifestError(f"{label} document-tree count is invalid")
        tree_digest = _text(
            record["tree_sha256"], label=f"{label} document-tree digest"
        )
        if not tree_digest.startswith(_SHA256_PREFIX) or len(tree_digest) != 71:
            raise CyclePreflightManifestError(
                f"{label} document-tree digest is invalid"
            )
        observed_tree = _document_tree_commitment(tree_path, label=label)
        expected_tree = _SHA256_PREFIX + (
            # contract-ratchet: allow frozen raw JSON-value tree commitment
            hashlib.sha256(
                canonical_json_value_bytes(
                    observed_tree,
                    error_type=CyclePreflightManifestError,
                    error_message=f"{label} document tree cannot be encoded",
                )
            ).hexdigest()
        )
        if (
            len(observed_tree) != record["document_count"]
            or expected_tree != tree_digest
        ):
            raise CyclePreflightManifestError(
                f"{label} document tree differs from commitment"
            )
    for input_path, digest in commitments.items():
        if input_path in mutable_paths:
            continue
        _verify_path(input_path, digest, label=f"{label} committed input")


def _document_tree_commitment(root: Path, *, label: str) -> dict[str, str]:
    """Return the canonical relative-path-to-digest map for a safe document tree."""

    if root.is_symlink() or not root.is_dir():
        raise CyclePreflightManifestError(f"{label} document tree is unavailable")
    observed: dict[str, str] = {}
    try:
        entries = tuple(sorted(root.rglob("*")))
    except OSError as exc:
        raise CyclePreflightManifestError(
            f"{label} document tree is unavailable"
        ) from exc
    for entry in entries:
        if entry.is_symlink() or not entry.is_file():
            if entry.is_dir():
                continue
            raise CyclePreflightManifestError(f"{label} document tree is unsafe")
        try:
            payload = read_unique_regular_file(entry)
        except (OSError, ReviewBundleError) as exc:
            raise CyclePreflightManifestError(
                f"{label} document tree is unsafe"
            ) from exc
        observed[entry.relative_to(root).as_posix()] = (
            _SHA256_PREFIX + hashlib.sha256(payload).hexdigest()
        )
    return observed


def _tree_root(card: Mapping[str, object], *, label: str) -> Path:
    """Locate the single directory output that anchors a document-tree commitment."""

    roots: list[Path] = []
    for path in _paths(card, field="output_paths", label=label):
        if path.is_symlink():
            continue
        try:
            if path.is_dir():
                roots.append(path)
        except OSError as exc:
            raise CyclePreflightManifestError(
                f"{label} output root is unavailable"
            ) from exc
    return _one(roots, label=f"{label} document-tree root")


def _verify_card_outputs(path: Path, card: Mapping[str, object], *, label: str) -> None:
    """Check each declared output, including the complete document tree exactly."""

    del path  # The card itself is authenticated by its parent or active stage head.
    outputs = _object(
        card.get("output_commitments"), label=f"{label} output commitments"
    )
    for name, raw in outputs.items():
        if isinstance(raw, str):
            if name.startswith("/"):
                _verify_path(Path(name), raw, label=f"{label} committed output")
                continue
            # Logical commitments (for example purchase state) are validated by
            # the historical replay rather than reinterpreted as file paths.
            if len(raw) != 64 or any(c not in "0123456789abcdef" for c in raw):
                raise CyclePreflightManifestError(f"{label} logical output is invalid")
            continue
        record = _object(raw, label=f"{label} {name} output")
        if set(record) == {"path", "sha256"}:
            output_path = Path(_text(record["path"], label=f"{label} {name} path"))
            if not output_path.is_absolute():
                raise CyclePreflightManifestError(
                    f"{label} output path is not absolute"
                )
            _verify_path(
                output_path,
                _text(record["sha256"], label=f"{label} {name} digest"),
                label=f"{label} committed output",
            )
            continue
        if name != "document_tree":
            raise CyclePreflightManifestError(f"{label} output commitment is malformed")
        tree_root = _tree_root(card, label=label)
        declared: dict[Path, str] = {}
        for relative, digest in record.items():
            if not isinstance(digest, str):
                raise CyclePreflightManifestError(
                    f"{label} document-tree entry is malformed"
                )
            relative_path = Path(relative)
            if relative_path.is_absolute() or ".." in relative_path.parts:
                raise CyclePreflightManifestError(
                    f"{label} document-tree entry escapes root"
                )
            declared[relative_path] = digest
            _verify_path(
                tree_root / relative_path, digest, label=f"{label} document tree"
            )
        try:
            actual: set[Path] = set()
            for candidate in tree_root.rglob("*"):
                if candidate.is_symlink():
                    raise CyclePreflightManifestError(
                        f"{label} document tree contains a symlink"
                    )
                if candidate.is_file():
                    actual.add(candidate.relative_to(tree_root))
        except OSError as exc:
            raise CyclePreflightManifestError(
                f"{label} document tree is unavailable"
            ) from exc
        if actual != set(declared):
            raise CyclePreflightManifestError(
                f"{label} document tree differs from commitment"
            )


def _verify_card_semantics(
    path: Path, card: Mapping[str, object], *, label: str
) -> None:
    """Authenticate run-card inputs and all committed outputs in one operation."""

    _verify_card_inputs(card, label=label)
    _verify_card_outputs(path, card, label=label)


def _verify_resolution_card(
    card: Mapping[str, object], *, ledger_path: Path, label: str
) -> None:
    """Verify the designated resolver while exempting only mutable SQLite bytes."""

    _verify_card_inputs(card, label=label, mutable_paths=frozenset({ledger_path}))
    _verify_card_outputs(Path("/unused"), card, label=label)


def _verify_terminal_resolution_transition(
    terminal_resolution: Path, *, historical_resolution: Path
) -> None:
    """Require source closure to name the resolver authenticated by replay."""

    if terminal_resolution != historical_resolution:
        raise CyclePreflightManifestError(
            "terminal resolution differs from historical replay transition"
        )


def _terminal_cards(
    initial_producer: Mapping[str, object], initial_descriptor: Mapping[str, object]
) -> tuple[Path, Path, Path]:
    """Derive the initial (root14/root27/root28) chain from producer inputs."""

    commitments = _committed_paths(initial_producer, label="v2 initial producer")
    cards = _committed_cards(commitments, label="v2 initial producer input")
    recovery_root = _text(
        initial_descriptor.get("recovery_root"), label="terminal recovery root"
    )
    clearance_path = Path(
        _text(
            initial_descriptor.get("purchased_clearance_run_card"),
            label="terminal clearance card",
        )
    )
    resolved_path = Path(
        _text(
            initial_descriptor.get("resolved_post_recovery_documents"),
            label="terminal resolved documents",
        )
    )
    recovery = _one(
        [
            path
            for path, card in cards
            if _stage(card) == "recover-recap-fetch-quarantine"
            and str(path.parent.parent) == recovery_root
        ],
        label="terminal recovery card",
    )
    clearance = _one(
        [
            path
            for path, card in cards
            if _stage(card) == "finalize-provenance-quarantine"
            and path == clearance_path
        ],
        label="terminal clearance card",
    )
    resolution = _one(
        [
            path
            for path, card in cards
            if _stage(card) == "resolve-post-recovery-documents"
            and path.parent.parent / "resolved-post-recovery-documents.jsonl"
            == resolved_path
        ],
        label="terminal resolution card",
    )
    return recovery, clearance, resolution


def _validate_descriptor(descriptor: Mapping[str, object]) -> None:
    """Reject malformed ordinal descriptors before using their path relationships."""

    ordinal = descriptor.get("ordinal")
    if ordinal == 0:
        expected = {
            "kind",
            "ordinal",
            "post_purchase_replay",
            "purchased_clearance",
            "purchased_clearance_run_card",
            "recovery_root",
            "resolved_post_recovery_documents",
            "selection",
        }
        if set(descriptor) != expected or descriptor.get("kind") != "initial_v2":
            raise CyclePreflightManifestError(
                "initial recovery descriptor is malformed"
            )
        replay = _object(
            descriptor.get("post_purchase_replay"), label="initial descriptor replay"
        )
        if set(replay) != {
            "cohort_policy",
            "prior_ranked_result",
            "prior_replacement_budget_plan",
            "prior_replacement_selection",
            "replacement_controlled_private_root",
            "replacement_purchase_authority",
        }:
            raise CyclePreflightManifestError(
                "initial recovery descriptor replay is malformed"
            )
        values = [*replay.values()]
    elif ordinal == 1:
        expected = {
            "kind",
            "ordinal",
            "purchased_clearance",
            "purchased_clearance_run_card",
            "recovery_root",
            "replacement_budget_plan",
            "replacement_controlled_private_root",
            "replacement_purchase_authority",
            "resolved_post_recovery_documents",
            "selection",
        }
        if set(descriptor) != expected or descriptor.get("kind") != "successor":
            raise CyclePreflightManifestError(
                "successor recovery descriptor is malformed"
            )
        values = [
            value for key, value in descriptor.items() if key not in {"kind", "ordinal"}
        ]
    else:
        raise CyclePreflightManifestError("recovery descriptor ordinal is invalid")
    if any(
        not isinstance(value, str) or not Path(value).is_absolute() for value in values
    ):
        raise CyclePreflightManifestError("recovery descriptor path is malformed")


def _committed_jsonl(
    path: Path, *, commitments: Mapping[Path, str], label: str
) -> tuple[Mapping[str, Any], ...]:
    """Read JSONL only after authenticating its enclosing card's commitment."""

    expected = commitments.get(path)
    if expected is None:
        raise CyclePreflightManifestError(f"{label} is not committed")
    try:
        payload = read_unique_regular_file(path)
    except (OSError, ReviewBundleError) as exc:
        raise CyclePreflightManifestError(f"{label} is unavailable or unsafe") from exc
    if hashlib.sha256(payload).hexdigest() != expected.removeprefix(_SHA256_PREFIX):
        raise CyclePreflightManifestError(f"{label} bytes differ from commitment")
    records: list[Mapping[str, Any]] = []
    for number, line in enumerate(payload.splitlines(), start=1):
        try:
            value = json.loads(line)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise CyclePreflightManifestError(
                f"{label} line {number} is not JSON"
            ) from exc
        if not isinstance(value, Mapping):
            raise CyclePreflightManifestError(f"{label} line {number} is not an object")
        records.append(cast(Mapping[str, Any], value))
    return tuple(records)


def _committed_output_path(
    card: Mapping[str, object],
    *,
    name: str,
    parent_commitments: Mapping[Path, str],
    label: str,
) -> Path:
    raw = _object(card.get("output_commitments"), label=f"{label} output commitments")
    record = _object(raw.get(name), label=f"{label} {name} commitment")
    raw_path = record.get("path")
    if not isinstance(raw_path, str):
        raise CyclePreflightManifestError(f"{label} {name} path is invalid")
    path = Path(raw_path)
    digest = _text(record.get("sha256"), label=f"{label} {name} digest")
    if (
        not digest.startswith(_SHA256_PREFIX)
        or len(digest) != len(_SHA256_PREFIX) + 64
        or parent_commitments.get(path) != digest
    ):
        raise CyclePreflightManifestError(f"{label} {name} path is not committed")
    return path


def reconstruct_historical_purchase_snapshots(
    slice_: NativeRecoverySlice,
    *,
    ledger_path: Path,
    policy_path: Path,
    initialization_receipt_path: Path,
) -> HistoricalPurchaseSnapshots:
    """Recover native historical states by reversing committed resolver records.

    The SQLite file is mutable implementation state, so this deliberately trusts
    neither its current byte hash nor a synthesized history.  It first requires
    the authenticated *logical* ledger state to equal the successor-source card,
    then reverses the two committed resolver transitions and verifies each exact
    historical state commitment.
    """

    policy = verify_case_dev_purchase_policy(
        _read_json(policy_path, label="purchase policy")
    )
    current = read_case_dev_purchase_snapshot(
        ledger_path,
        policy=policy,
        initialization_receipt_path=initialization_receipt_path,
    )
    source_card = _read_json(
        slice_.replacement_source_card, label="replacement source card"
    )
    expected_current = _text(
        source_card.get("purchase_state_sha256"),
        label="replacement source purchase state",
    )
    if current.purchase_state_sha256 != expected_current:
        raise CyclePreflightManifestError(
            "current logical purchase state differs from replacement source commitment"
        )
    source_commitments = _committed_paths(source_card, label="replacement source card")
    selected_resolution = _require_committed_card(
        slice_.resolution_card,
        commitments=source_commitments,
        label="selected resolution card",
    )
    selected_outputs = _object(
        selected_resolution.get("output_commitments"),
        label="selected resolution output commitments",
    )
    after_recovery_state = _text(
        selected_outputs.get("purchase_state_sha256"),
        label="selected resolution purchase state",
    )
    previous_resolutions: list[tuple[Path, Mapping[str, object]]] = []
    for path, card in _committed_cards(
        source_commitments, label="replacement source input"
    ):
        if (
            path == slice_.resolution_card
            or _stage(card) != "resolve-post-recovery-documents"
        ):
            continue
        outputs = _object(
            card.get("output_commitments"), label="prior resolution output commitments"
        )
        if outputs.get("purchase_state_sha256") == expected_current:
            previous_resolutions.append((path, card))
    _prior_resolution_path, prior_resolution = _one(
        previous_resolutions, label="prior committed resolution card"
    )
    prior_resolved_path = _committed_output_path(
        prior_resolution,
        name="resolved_post_recovery_documents",
        parent_commitments=source_commitments,
        label="prior resolution card",
    )
    selected_resolved_path = _committed_output_path(
        selected_resolution,
        name="resolved_post_recovery_documents",
        parent_commitments=source_commitments,
        label="selected resolution card",
    )
    try:
        after_recovery = reconstruct_pre_resolution_purchase_snapshot(
            current_snapshot=current,
            resolved_records=_committed_jsonl(
                prior_resolved_path,
                commitments=source_commitments,
                label="prior resolved documents",
            ),
            policy=policy,
            expected_purchase_state_before_sha256=after_recovery_state,
        )
        recovery_outputs = _object(
            _read_json(slice_.recovery_card, label="recovery card").get(
                "output_commitments"
            ),
            label="recovery output commitments",
        )
        before_recovery = reconstruct_pre_resolution_purchase_snapshot(
            current_snapshot=after_recovery,
            resolved_records=_committed_jsonl(
                selected_resolved_path,
                commitments=source_commitments,
                label="selected resolved documents",
            ),
            policy=policy,
            expected_purchase_state_before_sha256=_text(
                recovery_outputs.get("purchase_state_sha256"),
                label="recovery purchase state",
            ),
        )
    except ResolvedPostRecoveryError as exc:
        raise CyclePreflightManifestError(
            "committed resolver evidence cannot reconstruct historical purchase state"
        ) from exc
    return HistoricalPurchaseSnapshots(
        before_recovery=before_recovery,
        after_recovery=after_recovery,
        current=current,
        prior_resolution_card=_prior_resolution_path,
    )


def emit_discovery_sidecar(
    slice_: NativeRecoverySlice, *, index_path: Path, output: Path
) -> Path:
    """Write a non-authoritative discovery sidecar, refusing any replacement."""

    # Re-discover and verify immediately before writing.  The caller's slice is
    # not authority: it might have been observed before a mutable locator or a
    # selected card changed.
    refreshed = discover_native_recovery_slice(
        index_path=index_path, cycle_id=slice_.cycle_id
    )
    if refreshed != slice_:
        raise CyclePreflightManifestError("lineage changed before sidecar emission")
    _verify_v2_slice(refreshed)
    if (
        discover_native_recovery_slice(index_path=index_path, cycle_id=slice_.cycle_id)
        != refreshed
    ):
        raise CyclePreflightManifestError("lineage changed during sidecar emission")
    # A stable locator is insufficient: authenticated card contents may have
    # changed in place after the first semantic pass.
    _verify_v2_slice(refreshed)
    output = output.absolute()
    if output.exists() or output.is_symlink():
        raise CyclePreflightManifestError("sidecar output already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_json_bytes(
        {
            "schema_version": SIDECAR_SCHEMA,
            "non_authoritative": True,
            "cycle_id": slice_.cycle_id,
            "index_path": str(index_path.absolute()),
            "lineage_root_identity_sha256": slice_.lineage_root_identity_sha256,
            "native_cards": {
                "materialize": str(slice_.materialize_card),
                "consolidation": str(slice_.consolidation_card),
                "recovery": str(slice_.recovery_card),
                "clearance": str(slice_.clearance_card),
                "resolution": str(slice_.resolution_card),
                "replacement_source": str(slice_.replacement_source_card),
            },
        },
        error_type=CyclePreflightManifestError,
        error_message="could not encode discovery sidecar",
    )
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return output


def main(argv: Sequence[str] | None = None) -> int:
    """Discover native evidence and optionally emit only a non-authoritative sidecar."""

    parser = argparse.ArgumentParser(
        prog="python -m legalforecast.ingestion.cycle_preflight_manifest",
        description="Discover a provider-free Cycle 1 recovery preflight source set.",
    )
    parser.add_argument("--index", type=Path)
    parser.add_argument("--cycle-id")
    parser.add_argument("--emit-sidecar", type=Path)
    parser.add_argument("--verify-v2-sidecar", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.verify_v2_sidecar is not None:
            report = verify_v2_sidecar(
                args.verify_v2_sidecar, trusted_index_path=args.index
            )
            print(json.dumps(report, sort_keys=True) if args.json else "V2 PASS")
            return 0
        if args.index is None:
            parser.error("--index is required unless --verify-v2-sidecar is used")
        slice_ = discover_native_recovery_slice(
            index_path=args.index, cycle_id=args.cycle_id
        )
        sidecar = (
            emit_discovery_sidecar(
                slice_, index_path=args.index, output=args.emit_sidecar
            )
            if args.emit_sidecar
            else None
        )
    except CyclePreflightManifestError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    record: dict[str, Any] = {
        "schema_version": SIDECAR_SCHEMA,
        "non_authoritative": True,
        "cycle_id": slice_.cycle_id,
        "lineage_root_identity_sha256": slice_.lineage_root_identity_sha256,
        "sidecar": str(sidecar) if sidecar is not None else None,
    }
    print(
        json.dumps(record, sort_keys=True)
        if args.json
        else f"DISCOVERED {slice_.cycle_id}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
