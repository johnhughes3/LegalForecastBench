"""Adversarial union tests for repinned REST-promotion terminal evidence."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.ingestion.screening_snapshot_union import (
    ScreeningSnapshotUnionError,
    load_screening_snapshot_union,
)
from tests.test_rest_priority_subset_promotion import (
    _build_disjoint_ordinary_rest_snapshot,
    _build_promotion_fixture,
    _promote,
    _promoted_snapshot_path,
)


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


def _repin_snapshot(snapshot: Path, changed_files: tuple[str, ...]) -> str:
    manifest_path = snapshot / "manifest.json"
    manifest = cast(
        dict[str, Any], json.loads(manifest_path.read_text(encoding="utf-8"))
    )
    for filename in changed_files:
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
    return hashlib.sha256(manifest_path.read_bytes()).hexdigest()


def _mutate_accepted_evidence(snapshot: Path) -> tuple[str, ...]:
    candidates = _read_jsonl(snapshot / "candidates.jsonl")
    accepted = next(row for row in candidates if row["state"] == "accepted")
    accepted["evidence"]["selected_entries"][0]["text"] = "repinned altered motion"
    _write_jsonl(snapshot / "candidates.jsonl", candidates)
    screened = _read_jsonl(snapshot / "screened-cases.jsonl")
    screened[0]["selected_entries"][0]["text"] = "repinned altered motion"
    _write_jsonl(snapshot / "screened-cases.jsonl", screened)
    return ("candidates.jsonl", "screened-cases.jsonl")


def _mutate_accepted_anchor(snapshot: Path) -> tuple[str, ...]:
    candidates = _read_jsonl(snapshot / "candidates.jsonl")
    accepted = next(row for row in candidates if row["state"] == "accepted")
    accepted["evidence"]["eligibility_anchor_date"] = "2026-07-01"
    _write_jsonl(snapshot / "candidates.jsonl", candidates)
    screened = _read_jsonl(snapshot / "screened-cases.jsonl")
    screened[0]["eligibility_anchor_date"] = "2026-07-01"
    _write_jsonl(snapshot / "screened-cases.jsonl", screened)
    return ("candidates.jsonl", "screened-cases.jsonl")


def _mutate_accepted_state(snapshot: Path) -> tuple[str, ...]:
    candidates = _read_jsonl(snapshot / "candidates.jsonl")
    accepted = next(row for row in candidates if row["state"] == "accepted")
    accepted["state"] = "excluded"
    _write_jsonl(snapshot / "candidates.jsonl", candidates)
    screened = _read_jsonl(snapshot / "screened-cases.jsonl")
    exclusions = _read_jsonl(snapshot / "exclusions.jsonl")
    moved = screened.pop()
    moved.setdefault("reason", "strict_clean_screen_passed")
    moved.setdefault("primary_exclusion_reason", "strict_clean_screen_passed")
    exclusions.append(moved)
    _write_jsonl(snapshot / "screened-cases.jsonl", screened)
    _write_jsonl(snapshot / "exclusions.jsonl", exclusions)
    summary = cast(
        dict[str, Any],
        json.loads((snapshot / "summary.json").read_text(encoding="utf-8")),
    )
    summary["accepted_count"] -= 1
    summary["excluded_count"] += 1
    (snapshot / "summary.json").write_text(
        json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return (
        "candidates.jsonl",
        "screened-cases.jsonl",
        "exclusions.jsonl",
        "summary.json",
    )


def _mutate_accepted_reason(snapshot: Path) -> tuple[str, ...]:
    candidates = _read_jsonl(snapshot / "candidates.jsonl")
    accepted = next(row for row in candidates if row["state"] == "accepted")
    accepted["reason_code"] = "repinned_non_strict_reason"
    _write_jsonl(snapshot / "candidates.jsonl", candidates)
    return ("candidates.jsonl",)


def _mutate_exclusion_content(snapshot: Path) -> tuple[str, ...]:
    exclusions = _read_jsonl(snapshot / "exclusions.jsonl")
    exclusions[0]["detail"] = "repinned changed exclusion"
    _write_jsonl(snapshot / "exclusions.jsonl", exclusions)
    return ("exclusions.jsonl",)


@pytest.mark.parametrize(
    "mutate",
    (
        _mutate_accepted_evidence,
        _mutate_accepted_anchor,
        _mutate_accepted_state,
        _mutate_accepted_reason,
        _mutate_exclusion_content,
    ),
)
def test_union_rejects_repinned_promoted_terminal_or_ledger_tamper(
    tmp_path: Path,
    mutate: Callable[[Path], tuple[str, ...]],
) -> None:
    fixture = _build_promotion_fixture(tmp_path)
    _promote(fixture, tmp_path)
    promoted = _promoted_snapshot_path(tmp_path)
    ordinary = _build_disjoint_ordinary_rest_snapshot(fixture, tmp_path)
    promoted_manifest_sha256 = _repin_snapshot(promoted, mutate(promoted))

    with pytest.raises(ScreeningSnapshotUnionError):
        load_screening_snapshot_union(
            (ordinary, promoted),
            expected_manifest_sha256=(
                hashlib.sha256((ordinary / "manifest.json").read_bytes()).hexdigest(),
                promoted_manifest_sha256,
            ),
            expected_cycle_hash=fixture.cycle_hash,
        )
