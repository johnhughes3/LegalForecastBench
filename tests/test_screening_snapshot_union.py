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
    assert "candidate/source-manifest correction pin" in output
    assert "never infer authority from order or time" in output
    assert "unique active proof" in output
    assert "source-local raw bytes" in output
    assert "earliest UTC capture is the packet input" in output


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
        match="terminal evidence conflict requires an explicit authenticated",
    ):
        load_screening_snapshot_union(
            (first, second),
            expected_manifest_sha256=(
                _manifest_sha256(first),
                _manifest_sha256(second),
            ),
            expected_cycle_hash=_cycle_hash(tmp_path / "first"),
        )


def test_union_promotes_only_explicit_unique_active_correction_and_binds_its_raw(
    tmp_path: Path,
) -> None:
    candidate_id = "courtlistener-docket-73330395"
    stale = _snapshot(
        tmp_path / "stale",
        batch_id="baseline",
        observations=[
            (
                candidate_id,
                "excluded",
                "strict_clean_screen_failed",
                {
                    "candidate_id": candidate_id,
                    "reason": "procedural_or_standing_order",
                },
                b"<html><body>stale screen over docket with entry 12</body></html>",
            )
        ],
    )
    corrected_evidence = {
        "candidate_id": candidate_id,
        "first_written_mtd_disposition_date": "2026-06-30",
        "selected_entries": [{"entry_number": 12}],
        "motion_linkage": {"target_motion_entry_numbers": [8]},
    }
    corrected = _snapshot(
        tmp_path / "corrected",
        batch_id="current-policy-rescreen",
        observations=[
            (
                candidate_id,
                "accepted",
                "strict_clean_screen_passed",
                corrected_evidence,
                b"<html><body>corrected screen over docket with entry 12</body></html>",
            )
        ],
    )
    correction_hash = _manifest_sha256(corrected)
    kwargs = {
        "expected_terminal_correction_candidate_id": (candidate_id,),
        "expected_terminal_correction_source_manifest_sha256": (correction_hash,),
    }

    union = load_screening_snapshot_union(
        (stale, corrected),
        expected_manifest_sha256=(
            _manifest_sha256(stale),
            correction_hash,
        ),
        expected_cycle_hash=_cycle_hash(tmp_path / "stale"),
        **kwargs,
    )

    [candidate] = union.candidates
    assert candidate.state == "accepted"
    assert candidate.reason_code == "strict_clean_screen_passed"
    assert candidate.evidence == corrected_evidence
    assert len(union.raw_artifacts) == 2
    [canonical] = union.canonical_raw_artifacts
    assert canonical.content == (
        b"<html><body>corrected screen over docket with entry 12</body></html>"
    )
    correction = union.stage_commitment["longitudinal_corrections"][0]
    assert correction["candidate_id"] == candidate_id
    assert correction["canonical_source_manifest_sha256"] == correction_hash
    assert {row["state"] for row in correction["observations"]} == {
        "accepted",
        "excluded",
    }

    reversed_union = load_screening_snapshot_union(
        (corrected, stale),
        expected_manifest_sha256=(
            correction_hash,
            _manifest_sha256(stale),
        ),
        expected_cycle_hash=_cycle_hash(tmp_path / "stale"),
        **kwargs,
    )
    assert reversed_union.candidates == union.candidates
    assert (
        reversed_union.canonical_raw_artifacts[0].sha256
        == union.canonical_raw_artifacts[0].sha256
    )
    assert (
        reversed_union.stage_commitment["longitudinal_corrections"]
        == union.stage_commitment["longitudinal_corrections"]
    )


def test_union_command_archives_and_resumes_authenticated_terminal_correction(
    tmp_path: Path,
) -> None:
    candidate_id = "courtlistener-docket-73330395"
    stale_root = tmp_path / "stale"
    corrected_root = tmp_path / "corrected"
    stale = _snapshot(
        stale_root,
        batch_id="baseline",
        observations=[
            (
                candidate_id,
                "excluded",
                "strict_clean_screen_failed",
                {"candidate_id": candidate_id, "reason": "procedural"},
                b"<html><body>stale screen</body></html>",
            )
        ],
    )
    corrected = _snapshot(
        corrected_root,
        batch_id="rescreen",
        observations=[
            (
                candidate_id,
                "accepted",
                "strict_clean_screen_passed",
                {
                    "candidate_id": candidate_id,
                    "first_written_mtd_disposition_date": "2026-06-30",
                    "selected_entries": [{"entry_number": 12}],
                },
                b"<html><body>accepted source raw</body></html>",
            )
        ],
    )
    output_root = tmp_path / "union-output"
    snapshot_root = tmp_path / "union-snapshots"
    command = [
        "acquisition",
        "union-screening-snapshots",
        "--output-root",
        str(output_root),
        "--cycle-store",
        str(stale_root / "cycle.sqlite3"),
        "--batch-id",
        "longitudinal-union",
        "--expected-cycle-hash",
        _cycle_hash(stale_root),
        "--source-snapshot",
        str(stale),
        "--expected-source-snapshot-manifest-sha256",
        _manifest_sha256(stale),
        "--source-snapshot",
        str(corrected),
        "--expected-source-snapshot-manifest-sha256",
        _manifest_sha256(corrected),
        "--expected-terminal-correction-candidate-id",
        candidate_id,
        "--expected-terminal-correction-source-manifest-sha256",
        _manifest_sha256(corrected),
        "--snapshot-root",
        str(snapshot_root),
        "--snapshot-id",
        "complete-union",
        "--execute",
    ]

    assert cli_module.main(command) == 0
    snapshot = snapshot_root / "complete-union"
    [screened] = _jsonl(snapshot / "screened-cases.jsonl")
    assert screened["candidate_id"] == candidate_id
    archived = _jsonl(output_root / "union-terminal-observations.jsonl")
    assert len(archived) == 2
    assert sum(row["canonical_terminal_observation"] for row in archived) == 1
    [packet_raw] = _jsonl(output_root / "union-raw-artifacts.jsonl")
    assert (
        packet_raw["sha256"]
        == hashlib.sha256(b"<html><body>accepted source raw</body></html>").hexdigest()
    )
    cli_module._verify_packet_raw_artifacts_snapshot_binding(
        raw_html_dir=output_root / "union-raw-artifacts",
        raw_artifacts_manifest_path=output_root / "union-raw-artifacts.jsonl",
        screening_snapshot_manifest_path=snapshot / "manifest.json",
    )
    raw_directory, raw_paths = cli_module._verified_snapshot_raw_html_sources(
        snapshot,
        requested=output_root / "union-raw-artifacts",
        use_embedded_entries=True,
    )
    assert raw_directory is None
    assert raw_paths is not None
    assert raw_paths["73330395"].read_bytes() == (
        b"<html><body>accepted source raw</body></html>"
    )

    (output_root / "union-terminal-observations.jsonl").write_text("")
    assert cli_module.main(command) == 0
    assert _jsonl(output_root / "union-terminal-observations.jsonl") == archived

    shutil.rmtree(stale_root / "snapshots")
    shutil.rmtree(corrected_root / "snapshots")
    verify_snapshot(
        snapshot,
        expected_cycle_hash=_cycle_hash(stale_root),
        require_complete=True,
        require_saturated=True,
    )
    assert cli_module._owned_raw_records_from_snapshot(snapshot) == [packet_raw]

    manifest_path = snapshot / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    correction = manifest["stage_commitments"]["screening_snapshot_union_inputs"][
        "longitudinal_corrections"
    ][0]
    correction["observations"][0]["terminal_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(CycleAcquisitionStoreError, match="terminal hash drift"):
        cli_module._owned_raw_records_from_snapshot(snapshot)


def test_union_preserves_excluded_evidence_drift_under_explicit_source_authority(
    tmp_path: Path,
) -> None:
    candidate_id = "courtlistener-docket-69879510"
    failed_fetch = _snapshot(
        tmp_path / "failed-fetch",
        batch_id="baseline",
        observations=[
            (
                candidate_id,
                "excluded",
                "strict_clean_screen_failed",
                {
                    "candidate_id": candidate_id,
                    "reason": "fetch_failed",
                    "page_1_acquired": False,
                },
                b"<html><body>partial fetch</body></html>",
            )
        ],
    )
    substantive_evidence = {
        "candidate_id": candidate_id,
        "reason": "not_civil_cv_docket",
        "primary_exclusion_reason": "not_civil_cv_docket",
    }
    substantive = _snapshot(
        tmp_path / "substantive",
        batch_id="current-policy-rescreen",
        observations=[
            (
                candidate_id,
                "excluded",
                "strict_clean_screen_failed",
                substantive_evidence,
                b"<html><body>substantive screen</body></html>",
            )
        ],
    )

    union = load_screening_snapshot_union(
        (failed_fetch, substantive),
        expected_manifest_sha256=(
            _manifest_sha256(failed_fetch),
            _manifest_sha256(substantive),
        ),
        expected_cycle_hash=_cycle_hash(tmp_path / "failed-fetch"),
        expected_terminal_correction_candidate_id=(candidate_id,),
        expected_terminal_correction_source_manifest_sha256=(
            _manifest_sha256(substantive),
        ),
    )

    [candidate] = union.candidates
    assert candidate.state == "excluded"
    assert candidate.evidence == substantive_evidence
    [correction] = union.stage_commitment["longitudinal_corrections"]
    assert {row["evidence"]["reason"] for row in correction["observations"]} == {
        "fetch_failed",
        "not_civil_cv_docket",
    }


def test_union_rejects_unpinned_or_extra_longitudinal_corrections(
    tmp_path: Path,
) -> None:
    candidate_id = "courtlistener-docket-73330395"
    first = _snapshot(
        tmp_path / "first",
        batch_id="baseline",
        observations=[
            (
                candidate_id,
                "excluded",
                "strict_clean_screen_failed",
                {"candidate_id": candidate_id, "reason": "procedural"},
                b"<html><body>first</body></html>",
            )
        ],
    )
    second = _snapshot(
        tmp_path / "second",
        batch_id="rescreen",
        observations=[
            (
                candidate_id,
                "excluded",
                "strict_clean_screen_failed",
                {"candidate_id": candidate_id, "reason": "no_disposition"},
                b"<html><body>second</body></html>",
            )
        ],
    )
    common = {
        "source_snapshots": (first, second),
        "expected_manifest_sha256": (
            _manifest_sha256(first),
            _manifest_sha256(second),
        ),
        "expected_cycle_hash": _cycle_hash(tmp_path / "first"),
    }

    with pytest.raises(
        ScreeningSnapshotUnionError,
        match="requires an explicit authenticated correction source",
    ):
        load_screening_snapshot_union(**common)

    with pytest.raises(
        ScreeningSnapshotUnionError,
        match="correction pins do not exactly match terminal conflicts",
    ):
        load_screening_snapshot_union(
            **common,
            expected_terminal_correction_candidate_id=(candidate_id, "extra"),
            expected_terminal_correction_source_manifest_sha256=(
                _manifest_sha256(second),
                _manifest_sha256(first),
            ),
        )


def test_union_rejects_multiple_distinct_active_proofs_even_when_one_is_pinned(
    tmp_path: Path,
) -> None:
    candidate_id = "courtlistener-docket-73330395"
    first = _snapshot(
        tmp_path / "first",
        batch_id="first-screen",
        observations=[
            (
                candidate_id,
                "accepted",
                "strict_clean_screen_passed",
                {
                    "candidate_id": candidate_id,
                    "first_written_mtd_disposition_date": "2026-06-30",
                    "selected_entries": [{"entry_number": 12}],
                },
                b"<html><body>first active proof</body></html>",
            )
        ],
    )
    second = _snapshot(
        tmp_path / "second",
        batch_id="second-screen",
        observations=[
            (
                candidate_id,
                "accepted",
                "strict_clean_screen_passed",
                {
                    "candidate_id": candidate_id,
                    "first_written_mtd_disposition_date": "2026-07-01",
                    "selected_entries": [{"entry_number": 13}],
                },
                b"<html><body>second active proof</body></html>",
            )
        ],
    )

    with pytest.raises(
        ScreeningSnapshotUnionError,
        match="multiple non-identical active terminal proofs",
    ):
        load_screening_snapshot_union(
            (first, second),
            expected_manifest_sha256=(
                _manifest_sha256(first),
                _manifest_sha256(second),
            ),
            expected_cycle_hash=_cycle_hash(tmp_path / "first"),
            expected_terminal_correction_candidate_id=(candidate_id,),
            expected_terminal_correction_source_manifest_sha256=(
                _manifest_sha256(second),
            ),
        )


def test_union_rejects_active_correction_without_source_bound_raw(
    tmp_path: Path,
) -> None:
    candidate_id = "courtlistener-docket-73330395"
    first = _snapshot(
        tmp_path / "first",
        batch_id="baseline",
        observations=[
            (
                candidate_id,
                "excluded",
                "strict_clean_screen_failed",
                {"candidate_id": candidate_id, "reason": "procedural"},
                b"<html><body>first</body></html>",
            )
        ],
    )
    second = _snapshot(
        tmp_path / "second",
        batch_id="rescreen",
        observations=[
            (
                candidate_id,
                "accepted",
                "strict_clean_screen_passed",
                {
                    "candidate_id": candidate_id,
                    "first_written_mtd_disposition_date": "2026-06-30",
                    "selected_entries": [{"entry_number": 12}],
                },
                b"<html><body>second</body></html>",
            )
        ],
    )
    _rewrite_snapshot_jsonl(second, "raw-artifacts.jsonl", [])

    with pytest.raises(
        ScreeningSnapshotUnionError,
        match="active correction lacks exactly one source-bound raw artifact",
    ):
        load_screening_snapshot_union(
            (first, second),
            expected_manifest_sha256=(
                _manifest_sha256(first),
                _manifest_sha256(second),
            ),
            expected_cycle_hash=_cycle_hash(tmp_path / "first"),
            expected_terminal_correction_candidate_id=(candidate_id,),
            expected_terminal_correction_source_manifest_sha256=(
                _manifest_sha256(second),
            ),
        )


def test_union_rejects_source_raw_drift_within_unique_active_proof(
    tmp_path: Path,
) -> None:
    candidate_id = "courtlistener-docket-73330395"
    active_evidence = {
        "candidate_id": candidate_id,
        "first_written_mtd_disposition_date": "2026-06-30",
        "selected_entries": [{"entry_number": 12}],
    }
    first_active = _snapshot(
        tmp_path / "first-active",
        batch_id="first-active",
        observations=[
            (
                candidate_id,
                "accepted",
                "strict_clean_screen_passed",
                active_evidence,
                b"<html><body>active raw version one</body></html>",
            )
        ],
    )
    second_active = _snapshot(
        tmp_path / "second-active",
        batch_id="second-active",
        observations=[
            (
                candidate_id,
                "accepted",
                "strict_clean_screen_passed",
                active_evidence,
                b"<html><body>active raw version two</body></html>",
            )
        ],
    )
    excluded = _snapshot(
        tmp_path / "excluded",
        batch_id="baseline",
        observations=[
            (
                candidate_id,
                "excluded",
                "strict_clean_screen_failed",
                {"candidate_id": candidate_id, "reason": "procedural"},
                b"<html><body>excluded raw</body></html>",
            )
        ],
    )

    with pytest.raises(
        ScreeningSnapshotUnionError,
        match="active correction lacks exactly one source-bound raw artifact",
    ):
        load_screening_snapshot_union(
            (first_active, second_active, excluded),
            expected_manifest_sha256=(
                _manifest_sha256(first_active),
                _manifest_sha256(second_active),
                _manifest_sha256(excluded),
            ),
            expected_cycle_hash=_cycle_hash(tmp_path / "first-active"),
            expected_terminal_correction_candidate_id=(candidate_id,),
            expected_terminal_correction_source_manifest_sha256=(
                _manifest_sha256(first_active),
            ),
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


def test_union_rejects_uncommitted_raw_path_before_reading_referenced_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    sentinel = (tmp_path / "must-not-be-read.html").resolve()
    sentinel.write_bytes(b"<html><body>uncommitted local file</body></html>")
    [raw_record] = _jsonl(first / "raw-artifacts.jsonl")
    raw_record["path"] = str(sentinel)
    # Deliberately do not update manifest.json: the metadata is unauthenticated.
    (first / "raw-artifacts.jsonl").write_text(json.dumps(raw_record) + "\n")

    original_read_bytes = Path.read_bytes
    referenced_file_reads: list[Path] = []

    def guarded_read_bytes(path: Path) -> bytes:
        if path.resolve() == sentinel:
            referenced_file_reads.append(path)
            raise AssertionError("unauthenticated raw path was read")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)

    with pytest.raises(
        SnapshotVerificationError,
        match=r"snapshot file commitment mismatch: raw-artifacts\.jsonl",
    ):
        load_screening_snapshot_union(
            (first, second),
            expected_manifest_sha256=(
                _manifest_sha256(first),
                _manifest_sha256(second),
            ),
            expected_cycle_hash=_cycle_hash(tmp_path / "first"),
        )
    assert referenced_file_reads == []


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
