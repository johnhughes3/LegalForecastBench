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

from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseSnapshot,
    read_case_dev_purchase_snapshot,
    verify_case_dev_purchase_policy,
)
from legalforecast.ingestion.cycle_lineage_index import (
    CycleLineageIndexError,
    _authenticate_stage_head_entry,  # pyright: ignore[reportPrivateUsage]
    _load_index,  # pyright: ignore[reportPrivateUsage]
    locate_cycle_lineage,
)
from legalforecast.ingestion.disclosure_review_bundle import (
    ReviewBundleError,
    read_unique_regular_file,
)
from legalforecast.ingestion.resolved_post_recovery import (
    ResolvedPostRecoveryError,
    reconstruct_pre_resolution_purchase_snapshot,
)

SIDECAR_SCHEMA = "legalforecast.cycle_preflight_manifest_sidecar.v1"
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
    materialize = _one(
        [
            Path(cast(str, head["run_card_path"]))
            for head in chain
            if head["stage"] == "materialize-cohort-documents"
        ],
        label="materialize stage head",
    )
    materialize_card = _read_json(materialize, label="materialize run card")
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
    )


def emit_discovery_sidecar(slice_: NativeRecoverySlice, *, output: Path) -> Path:
    """Write a non-authoritative discovery sidecar, refusing any replacement."""

    output = output.absolute()
    if output.exists() or output.is_symlink():
        raise CyclePreflightManifestError("sidecar output already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_json_bytes(
        {
            "schema_version": SIDECAR_SCHEMA,
            "non_authoritative": True,
            "cycle_id": slice_.cycle_id,
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
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--cycle-id")
    parser.add_argument("--emit-sidecar", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        slice_ = discover_native_recovery_slice(
            index_path=args.index, cycle_id=args.cycle_id
        )
        sidecar = (
            emit_discovery_sidecar(slice_, output=args.emit_sidecar)
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
