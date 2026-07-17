from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import legalforecast.cli as cli_module
import pytest
from legalforecast.ingestion.cycle_acquisition_store import (
    CycleAcquisitionStore,
    CycleAcquisitionStoreError,
    SnapshotVerificationError,
    verify_snapshot,
)
from legalforecast.ingestion.discovery_scheduler import (
    DiscoveryHit,
    TermTerminalStatus,
)
from legalforecast.ingestion.screening_snapshot_union import (
    ScreeningSnapshotUnionError,
    load_screening_snapshot_union,
)

_CYCLE_POLICY = {"eligibility_anchor": "2026-06-30", "fixture": True}


def test_union_help_documents_raw_observation_policy(capsys: Any) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli_module.main(["acquisition", "union-screening-snapshots", "--help"])
    assert exc_info.value.code == 0

    output = capsys.readouterr().out
    assert "excluded duplicates" in output
    assert "distinct authenticated raw docket observations" in output
    assert "UTC capture is the canonical packet input" in output
    assert "Accepted/newly-free duplicates" in output
    assert "require identical raw bytes" in output


def test_union_preserves_updated_raw_observations_for_identical_terminal_evidence(
    tmp_path: Path,
) -> None:
    candidate_id = "courtlistener-docket-61568804"
    evidence = {
        "candidate_id": candidate_id,
        "reason": "no_mtd_or_rule_12_reference",
        "primary_exclusion_reason": "no_mtd_or_rule_12_reference",
    }
    first = _snapshot(
        tmp_path / "first",
        batch_id="baseline",
        observations=[
            (
                candidate_id,
                "excluded",
                "strict_clean_screen_failed",
                evidence,
                b"<html><body>earlier docket observation</body></html>",
            )
        ],
    )
    second = _snapshot(
        tmp_path / "second",
        batch_id="terminal-firecrawl",
        observations=[
            (
                candidate_id,
                "excluded",
                "strict_clean_screen_failed",
                evidence,
                b"<html><body>later docket observation</body></html>",
            )
        ],
    )

    union = load_screening_snapshot_union(
        (first, second),
        expected_manifest_sha256=(_manifest_sha256(first), _manifest_sha256(second)),
        expected_cycle_hash=_cycle_hash(tmp_path / "first"),
    )

    assert [candidate.candidate_id for candidate in union.candidates] == [candidate_id]
    assert len(union.raw_artifacts) == 2
    assert {artifact.content for artifact in union.raw_artifacts} == {
        b"<html><body>earlier docket observation</body></html>",
        b"<html><body>later docket observation</body></html>",
    }
    assert [artifact.sha256 for artifact in union.raw_artifacts] == sorted(
        artifact.sha256 for artifact in union.raw_artifacts
    )
    [canonical] = union.canonical_raw_artifacts
    assert canonical.content == b"<html><body>earlier docket observation</body></html>"

    reversed_union = load_screening_snapshot_union(
        (second, first),
        expected_manifest_sha256=(_manifest_sha256(second), _manifest_sha256(first)),
        expected_cycle_hash=_cycle_hash(tmp_path / "first"),
    )
    assert reversed_union.canonical_raw_artifacts[0].sha256 == canonical.sha256


def test_union_archives_excluded_versions_but_projects_earliest_for_packets(
    tmp_path: Path,
) -> None:
    candidate_id = "courtlistener-docket-61568804"
    evidence = {
        "candidate_id": candidate_id,
        "reason": "no_mtd_or_rule_12_reference",
    }
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first = _snapshot(
        first_root,
        batch_id="baseline",
        observations=[
            (
                candidate_id,
                "excluded",
                "strict_clean_screen_failed",
                evidence,
                b"<html><body>earlier docket observation</body></html>",
            )
        ],
    )
    second = _snapshot(
        second_root,
        batch_id="terminal-firecrawl",
        observations=[
            (
                candidate_id,
                "excluded",
                "strict_clean_screen_failed",
                evidence,
                b"<html><body>later docket observation</body></html>",
            )
        ],
    )
    cycle_hash = _cycle_hash(first_root)
    output_root = tmp_path / "union-output"
    snapshot_root = tmp_path / "union-snapshots"
    command = [
        "acquisition",
        "union-screening-snapshots",
        "--output-root",
        str(output_root),
        "--cycle-store",
        str(first_root / "cycle.sqlite3"),
        "--batch-id",
        "raw-observation-union",
        "--expected-cycle-hash",
        cycle_hash,
        "--source-snapshot",
        str(first),
        "--expected-source-snapshot-manifest-sha256",
        _manifest_sha256(first),
        "--source-snapshot",
        str(second),
        "--expected-source-snapshot-manifest-sha256",
        _manifest_sha256(second),
        "--snapshot-root",
        str(snapshot_root),
        "--snapshot-id",
        "complete-union",
        "--execute",
    ]

    assert cli_module.main(command) == 0
    union_snapshot = snapshot_root / "complete-union"
    assert len(_jsonl(union_snapshot / "raw-artifacts.jsonl")) == 2
    canonical_records = _jsonl(output_root / "union-raw-artifacts.jsonl")
    observation_records = _jsonl(output_root / "union-raw-observations.jsonl")
    assert len(canonical_records) == 1
    assert len(observation_records) == 2
    assert canonical_records[0]["retrieved_at"] == "2026-07-16T12:00:00Z"
    assert (
        canonical_records[0]["sha256"]
        == hashlib.sha256(
            b"<html><body>earlier docket observation</body></html>"
        ).hexdigest()
    )

    (output_root / "union-raw-artifacts.jsonl").unlink()
    (output_root / "union-raw-observations.jsonl").write_text("")
    assert cli_module.main(command) == 0
    assert _jsonl(output_root / "union-raw-artifacts.jsonl") == canonical_records
    assert _jsonl(output_root / "union-raw-observations.jsonl") == observation_records

    shutil.rmtree(first_root / "snapshots")
    shutil.rmtree(second_root)
    verify_snapshot(
        union_snapshot,
        expected_cycle_hash=cycle_hash,
        require_complete=True,
        require_saturated=True,
    )
    cli_module._verify_packet_raw_artifacts_snapshot_binding(
        raw_html_dir=output_root / "union-raw-artifacts",
        raw_artifacts_manifest_path=output_root / "union-raw-artifacts.jsonl",
        screening_snapshot_manifest_path=union_snapshot / "manifest.json",
    )

    manifest_path = union_snapshot / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    mapping = manifest["stage_commitments"]["screening_snapshot_union_inputs"][
        "canonical_raw_artifacts"
    ]
    mapping[0]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(
        CycleAcquisitionStoreError,
        match="does not select the earliest authenticated observation",
    ):
        cli_module._owned_raw_records_from_snapshot(union_snapshot)


def test_union_rejects_active_candidate_with_divergent_raw_observations(
    tmp_path: Path,
) -> None:
    candidate_id = "courtlistener-docket-61568804"
    evidence = {"candidate_id": candidate_id, "selected_entries": [16]}
    first = _snapshot(
        tmp_path / "first",
        batch_id="baseline",
        observations=[
            (
                candidate_id,
                "accepted",
                "strict_clean_screen_passed",
                evidence,
                b"<html><body>earlier docket observation</body></html>",
            )
        ],
    )
    second = _snapshot(
        tmp_path / "second",
        batch_id="terminal-firecrawl",
        observations=[
            (
                candidate_id,
                "accepted",
                "strict_clean_screen_passed",
                evidence,
                b"<html><body>later docket observation</body></html>",
            )
        ],
    )

    with pytest.raises(
        ScreeningSnapshotUnionError,
        match="active candidate has non-identical raw-artifact commitments",
    ):
        load_screening_snapshot_union(
            (first, second),
            expected_manifest_sha256=(
                _manifest_sha256(first),
                _manifest_sha256(second),
            ),
            expected_cycle_hash=_cycle_hash(tmp_path / "first"),
        )


def test_union_rejects_updated_raw_observations_with_conflicting_terminal_evidence(
    tmp_path: Path,
) -> None:
    candidate_id = "courtlistener-docket-61568804"
    first = _snapshot(
        tmp_path / "first",
        batch_id="baseline",
        observations=[
            (
                candidate_id,
                "excluded",
                "strict_clean_screen_failed",
                {
                    "candidate_id": candidate_id,
                    "reason": "no_mtd_or_rule_12_reference",
                },
                b"<html><body>earlier docket observation</body></html>",
            )
        ],
    )
    second = _snapshot(
        tmp_path / "second",
        batch_id="terminal-firecrawl",
        observations=[
            (
                candidate_id,
                "accepted",
                "strict_clean_screen_passed",
                {"candidate_id": candidate_id, "selected_entries": [16]},
                b"<html><body>later docket observation</body></html>",
            )
        ],
    )

    with pytest.raises(
        ScreeningSnapshotUnionError,
        match="non-identical terminal evidence",
    ):
        load_screening_snapshot_union(
            (first, second),
            expected_manifest_sha256=(
                _manifest_sha256(first),
                _manifest_sha256(second),
            ),
            expected_cycle_hash=_cycle_hash(tmp_path / "first"),
        )


def test_union_rejects_cross_candidate_raw_path_substitution(tmp_path: Path) -> None:
    first = _snapshot(
        tmp_path / "first",
        batch_id="baseline",
        observations=[
            (
                "courtlistener-docket-61568804",
                "excluded",
                "strict_clean_screen_failed",
                {
                    "candidate_id": "courtlistener-docket-61568804",
                    "reason": "no_mtd_or_rule_12_reference",
                },
                b"<html><body>docket 61568804</body></html>",
            ),
            (
                "courtlistener-docket-61568805",
                "excluded",
                "strict_clean_screen_failed",
                {
                    "candidate_id": "courtlistener-docket-61568805",
                    "reason": "no_mtd_or_rule_12_reference",
                },
                b"<html><body>docket 61568805</body></html>",
            ),
        ],
    )
    raw_records = _jsonl(first / "raw-artifacts.jsonl")
    raw_records[0]["candidate_id"], raw_records[1]["candidate_id"] = (
        raw_records[1]["candidate_id"],
        raw_records[0]["candidate_id"],
    )
    _rewrite_snapshot_jsonl(first, "raw-artifacts.jsonl", raw_records)
    second = _snapshot(
        tmp_path / "second",
        batch_id="terminal-firecrawl",
        observations=[
            (
                "courtlistener-docket-61568806",
                "excluded",
                "strict_clean_screen_failed",
                {
                    "candidate_id": "courtlistener-docket-61568806",
                    "reason": "no_mtd_or_rule_12_reference",
                },
                b"<html><body>docket 61568806</body></html>",
            )
        ],
    )

    with pytest.raises(ScreeningSnapshotUnionError, match="ownership mismatch"):
        load_screening_snapshot_union(
            (first, second),
            expected_manifest_sha256=(
                _manifest_sha256(first),
                _manifest_sha256(second),
            ),
            expected_cycle_hash=_cycle_hash(tmp_path / "first"),
        )


def test_union_rejects_cross_source_raw_owner_substitution(tmp_path: Path) -> None:
    first_id = "courtlistener-docket-61568804"
    second_id = "courtlistener-docket-61568805"
    first = _snapshot(
        tmp_path / "first",
        batch_id="baseline",
        observations=[
            (
                first_id,
                "excluded",
                "strict_clean_screen_failed",
                {"candidate_id": first_id, "reason": "no_mtd_reference"},
                b"<html><body>docket 61568804</body></html>",
            )
        ],
    )
    second = _snapshot(
        tmp_path / "second",
        batch_id="terminal-firecrawl",
        observations=[
            (
                second_id,
                "excluded",
                "strict_clean_screen_failed",
                {"candidate_id": second_id, "reason": "no_mtd_reference"},
                b"<html><body>docket 61568805</body></html>",
            )
        ],
    )
    [raw_record] = _jsonl(first / "raw-artifacts.jsonl")
    old_path = Path(raw_record["path"])
    substituted_path = old_path.with_name("61568805.html")
    old_path.rename(substituted_path)
    raw_record["candidate_id"] = second_id
    raw_record["path"] = str(substituted_path)
    _rewrite_snapshot_jsonl(first, "raw-artifacts.jsonl", [raw_record])

    with pytest.raises(
        SnapshotVerificationError,
        match=r"raw-artifacts\.jsonl references unknown candidate_id.*61568805",
    ):
        load_screening_snapshot_union(
            (first, second),
            expected_manifest_sha256=(
                _manifest_sha256(first),
                _manifest_sha256(second),
            ),
            expected_cycle_hash=_cycle_hash(tmp_path / "first"),
        )


def _snapshot(
    root: Path,
    *,
    batch_id: str,
    observations: list[tuple[str, str, str, dict[str, Any], bytes]],
) -> Path:
    store_path = root / "cycle.sqlite3"
    term = "fixture-term"
    raw_root = root / "raw"
    raw_root.mkdir(parents=True)
    with CycleAcquisitionStore(store_path) as store:
        store.ensure_cycle(_CYCLE_POLICY)
        store.ensure_batch(batch_id, {"source": batch_id})
        store.ensure_terms(batch_id, (term,))
        store.commit_search_page(
            batch_id,
            term,
            None,
            tuple(
                DiscoveryHit(
                    provider_hit_id=f"{batch_id}:{candidate_id}",
                    candidate_id=candidate_id,
                    payload={"candidate_id": candidate_id},
                )
                for candidate_id, _state, _reason, _evidence, _content in observations
            ),
            next_cursor=None,
            terminal_status=TermTerminalStatus.EXHAUSTED,
        )
        for index, (candidate_id, state, reason, evidence, content) in enumerate(
            observations
        ):
            store.record_observation(
                candidate_id,
                batch_id=batch_id,
                state=state,
                reason_code=reason,
                evidence=evidence,
                observed_at="2026-07-16T12:00:00Z",
            )
            docket_id = candidate_id.removeprefix("courtlistener-docket-")
            raw_path = raw_root / f"{docket_id}.html"
            store.write_raw_artifact(
                candidate_id,
                raw_path,
                content,
                retrieved_at=(
                    f"2026-07-16T12:00:0{index}Z"
                    if batch_id == "baseline"
                    else f"2026-07-16T13:00:0{index}Z"
                ),
            )
        return store.export_snapshot(
            root / "snapshots",
            snapshot_id=f"{batch_id}-complete",
            batch_id=batch_id,
            complete=True,
        )


def _manifest_sha256(snapshot: Path) -> str:
    return hashlib.sha256((snapshot / "manifest.json").read_bytes()).hexdigest()


def _cycle_hash(root: Path) -> str:
    with CycleAcquisitionStore(root / "cycle.sqlite3") as store:
        return store.cycle_hash


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def _rewrite_snapshot_jsonl(
    snapshot: Path,
    filename: str,
    records: list[dict[str, Any]],
) -> None:
    payload = b"".join(
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        for record in records
    )
    (snapshot / filename).write_bytes(payload)
    manifest_path = snapshot / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"][filename] = {
        "sha256": hashlib.sha256(payload).hexdigest(),
        "byte_count": len(payload),
        "row_count": len(records),
    }
    manifest_path.write_text(json.dumps(manifest))
