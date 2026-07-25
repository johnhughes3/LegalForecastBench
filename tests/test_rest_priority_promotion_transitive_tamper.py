"""Transitive evidence checks for REST promotions embedded in unions."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore
from legalforecast.ingestion.firecrawl_screening_identity import (
    FirecrawlScreeningIdentityError,
    validate_rest_terminal_subset_promotions_in_snapshot,
)
from legalforecast.ingestion.screening_snapshot_union import (
    ScreeningSnapshotUnionError,
    load_screening_snapshot_union,
)
from tests.test_rest_priority_subset_promotion import (
    _ANCHOR_TEXT,
    _build_disjoint_ordinary_rest_snapshot,
    _build_promotion_fixture,
    _promote,
    _promoted_snapshot_path,
)


def _manifest_sha256(snapshot: Path) -> str:
    return hashlib.sha256((snapshot / "manifest.json").read_bytes()).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        cast(dict[str, Any], json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def _repin(snapshot: Path, filenames: tuple[str, ...]) -> str:
    manifest_path = snapshot / "manifest.json"
    manifest = cast(
        dict[str, Any], json.loads(manifest_path.read_text(encoding="utf-8"))
    )
    for filename in filenames:
        payload = (snapshot / filename).read_bytes()
        manifest["files"][filename] = {
            "sha256": hashlib.sha256(payload).hexdigest(),
            "byte_count": len(payload),
            "row_count": payload.count(b"\n"),
        }
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return _manifest_sha256(snapshot)


def _materialize_nested_union(
    *,
    store_path: Path,
    snapshots: tuple[Path, Path],
    cycle_hash: str,
    output_root: Path,
) -> Path:
    union = load_screening_snapshot_union(
        snapshots,
        expected_manifest_sha256=tuple(_manifest_sha256(path) for path in snapshots),
        expected_cycle_hash=cycle_hash,
    )
    batch_id = "nested-rest-promotion-union"
    term = "nested-union"
    with CycleAcquisitionStore(store_path) as store:
        store.ensure_batch(
            batch_id,
            {
                "provider": "none",
                "query_terms": [term],
                "provider_activity_requested": False,
            },
        )
        store.ensure_terms(batch_id, (term,))
        store.commit_search_page(
            batch_id,
            term,
            None,
            tuple(
                {
                    "provider_hit_id": f"nested-{candidate.candidate_id}",
                    "candidate_id": candidate.candidate_id,
                    "payload": {"candidate_id": candidate.candidate_id},
                }
                for candidate in union.candidates
            ),
            next_cursor=None,
            terminal_status="exhausted",
        )
        for candidate in union.candidates:
            current = store.current_observation(candidate.candidate_id)
            assert current is not None
            store.reuse_current_terminal_observation(
                candidate.candidate_id,
                batch_id=batch_id,
                source_observation=current,
            )
        return store.export_snapshot(
            output_root,
            snapshot_id="nested-union-snapshot",
            batch_id=batch_id,
            complete=True,
            stage_commitments={
                "screening_snapshot_union_inputs": dict(union.stage_commitment)
            },
            use_batch_terminal_observations=True,
        )


def _build_disjoint_exclusion(tmp_path: Path) -> tuple[Path, str]:
    store_path = tmp_path / "disjoint.sqlite3"
    candidate_id = "courtlistener-docket-888"
    with CycleAcquisitionStore(store_path) as store:
        store.ensure_cycle(
            {
                "schema_version": "test-cycle",
                "eligibility_anchor": _ANCHOR_TEXT,
            }
        )
        store.ensure_batch("disjoint", {"provider": "courtlistener"})
        store.ensure_terms("disjoint", ("screen",))
        store.commit_search_page(
            "disjoint",
            "screen",
            None,
            (
                {
                    "provider_hit_id": "disjoint-888",
                    "candidate_id": candidate_id,
                    "payload": {"candidate_id": candidate_id},
                },
            ),
            next_cursor=None,
            terminal_status="exhausted",
        )
        store.record_observation(
            candidate_id,
            batch_id="disjoint",
            state="excluded",
            reason_code="decision_before_release_anchor",
            evidence={
                "candidate_id": candidate_id,
                "decision_date": "2026-06-29",
            },
        )
        snapshot = store.export_snapshot(
            tmp_path / "disjoint-snapshots",
            snapshot_id="disjoint-terminal",
            batch_id="disjoint",
            complete=True,
            stage_commitments={
                "courtlistener_rest_screen_inputs": {
                    "schema_version": (
                        "legalforecast.courtlistener_rest_screen_inputs.v1"
                    )
                }
            },
        )
    return snapshot, _manifest_sha256(snapshot)


@pytest.mark.parametrize("tamper", ("evidence", "anchor"))
def test_nested_union_rejects_repinned_rest_promotion_evidence_tamper(
    tmp_path: Path,
    tamper: str,
) -> None:
    fixture = _build_promotion_fixture(tmp_path)
    _promote(fixture, tmp_path)
    promoted = _promoted_snapshot_path(tmp_path)
    ordinary = _build_disjoint_ordinary_rest_snapshot(fixture, tmp_path)
    nested = _materialize_nested_union(
        store_path=fixture.store_path,
        snapshots=(ordinary, promoted),
        cycle_hash=fixture.cycle_hash,
        output_root=tmp_path / "nested-output",
    )
    candidates = _read_jsonl(nested / "candidates.jsonl")
    accepted = next(
        row for row in candidates if row["candidate_id"] == fixture.accepted_id
    )
    screened = _read_jsonl(nested / "screened-cases.jsonl")
    accepted_screened = next(
        row for row in screened if row["candidate_id"] == fixture.accepted_id
    )
    if tamper == "evidence":
        accepted["evidence"]["selected_entries"][0]["text"] = "nested repinned change"
        accepted_screened["selected_entries"][0]["text"] = "nested repinned change"
    else:
        accepted["evidence"]["eligibility_anchor_date"] = "2026-07-01"
        accepted_screened["eligibility_anchor_date"] = "2026-07-01"
    _write_jsonl(nested / "candidates.jsonl", candidates)
    _write_jsonl(nested / "screened-cases.jsonl", screened)
    nested_manifest_sha256 = _repin(
        nested, ("candidates.jsonl", "screened-cases.jsonl")
    )
    disjoint, disjoint_manifest_sha256 = _build_disjoint_exclusion(tmp_path)

    with pytest.raises(ScreeningSnapshotUnionError):
        load_screening_snapshot_union(
            (nested, disjoint),
            expected_manifest_sha256=(
                nested_manifest_sha256,
                disjoint_manifest_sha256,
            ),
            expected_cycle_hash=fixture.cycle_hash,
        )


@pytest.mark.parametrize("shape", ("promotion_plus_union", "duplicate_leaf"))
def test_transitive_validator_rejects_ambiguous_or_overlapping_promotion_leaves(
    tmp_path: Path,
    shape: str,
) -> None:
    fixture = _build_promotion_fixture(tmp_path)
    _promote(fixture, tmp_path)
    promoted = _promoted_snapshot_path(tmp_path)
    manifest = cast(
        dict[str, Any],
        json.loads((promoted / "manifest.json").read_text(encoding="utf-8")),
    )
    direct_stage = cast(dict[str, object], manifest["stage_commitments"])
    source = {"stage_commitments": direct_stage}
    union = {
        "schema_version": "legalforecast.screening_snapshot_union_inputs.v2",
        "sources": [source, source],
    }
    stage = (
        {**direct_stage, "screening_snapshot_union_inputs": union}
        if shape == "promotion_plus_union"
        else {"screening_snapshot_union_inputs": union}
    )

    with pytest.raises(FirecrawlScreeningIdentityError):
        validate_rest_terminal_subset_promotions_in_snapshot(
            stage,
            snapshot_candidates=_read_jsonl(promoted / "candidates.jsonl"),
            snapshot_screened=_read_jsonl(promoted / "screened-cases.jsonl"),
            snapshot_exclusions=_read_jsonl(promoted / "exclusions.jsonl"),
        )
