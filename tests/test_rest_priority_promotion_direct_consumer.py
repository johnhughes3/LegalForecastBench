"""Direct downstream admission checks for REST priority promotions."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

import legalforecast.cli as cli_module
import pytest
from tests.test_rest_priority_subset_promotion import (
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


def _repin_manifest_files(snapshot: Path, filenames: tuple[str, ...]) -> None:
    manifest_path = snapshot / "manifest.json"
    manifest = cast(
        dict[str, Any],
        json.loads(manifest_path.read_text(encoding="utf-8")),
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


def test_plan_public_downloads_rejects_repinned_lineage_stripping(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = _build_promotion_fixture(tmp_path)
    _promote(fixture, tmp_path)
    promoted = _promoted_snapshot_path(tmp_path)
    original_manifest_sha256 = hashlib.sha256(
        (promoted / "manifest.json").read_bytes()
    ).hexdigest()
    candidates = _read_jsonl(promoted / "candidates.jsonl")
    screened = _read_jsonl(promoted / "screened-cases.jsonl")
    accepted_candidate = next(
        row for row in candidates if row["candidate_id"] == fixture.accepted_id
    )
    accepted_screened = next(
        row for row in screened if row["candidate_id"] == fixture.accepted_id
    )
    accepted_candidate["evidence"]["eligibility_anchor_date"] = "2025-01-01"
    accepted_screened["eligibility_anchor_date"] = "2025-01-01"
    _write_jsonl(promoted / "candidates.jsonl", candidates)
    _write_jsonl(promoted / "screened-cases.jsonl", screened)
    _repin_manifest_files(
        promoted,
        ("candidates.jsonl", "screened-cases.jsonl"),
    )
    manifest_path = promoted / "manifest.json"
    manifest = cast(
        dict[str, Any],
        json.loads(manifest_path.read_text(encoding="utf-8")),
    )
    manifest["stage_commitments"] = {
        "courtlistener_rest_screen_inputs": {
            "schema_version": "legalforecast.courtlistener_rest_screen_inputs.v1"
        }
    }
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    assert (
        cli_module.main(
            [
                "acquisition",
                "plan-public-downloads",
                "--output-root",
                str(tmp_path / "plan-public-output"),
                "--snapshot",
                str(promoted),
                "--expected-cycle-hash",
                fixture.cycle_hash,
                "--expected-snapshot-manifest-sha256",
                original_manifest_sha256,
                "--use-embedded-entries",
            ]
        )
        == 2
    )
    error = capsys.readouterr().err
    assert "externally frozen pin" in error
