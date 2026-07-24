from __future__ import annotations

import hashlib
import json
import os
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any

import legalforecast.cli as cli_module
import legalforecast.ingestion.screening_snapshot_union as union_module
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
from legalforecast.ingestion.firecrawl_screening_identity import (
    firecrawl_screening_implementation,
)
from legalforecast.ingestion.screening_snapshot_union import (
    ScreeningSnapshotUnionError,
    load_screening_snapshot_union,
)
from legalforecast.ingestion.strict_screen_evidence import (
    StrictScreenEvidenceError,
    validate_strict_screen_evidence,
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


def test_regular_file_reader_sets_close_on_exec(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "payload.json"
    path.write_bytes(b"{}")
    original_open = os.open
    observed_flags: list[int] = []

    def recording_open(open_path: Path, flags: int) -> int:
        observed_flags.append(flags)
        return original_open(open_path, flags)

    monkeypatch.setattr(union_module.os, "open", recording_open)

    assert union_module._read_regular_file(path, "fixture") == b"{}"
    assert observed_flags
    close_on_exec = getattr(os, "O_CLOEXEC", 0)
    if close_on_exec:
        assert observed_flags[0] & close_on_exec


def test_union_rejects_source_without_stage_commitments(tmp_path: Path) -> None:
    first = _snapshot(
        tmp_path / "first",
        batch_id="first",
        observations=[],
    )
    second = _snapshot(
        tmp_path / "second",
        batch_id="second",
        observations=[],
    )
    manifest_path = first / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest.pop("stage_commitments")
    manifest_path.write_text(json.dumps(manifest))

    with pytest.raises(
        ScreeningSnapshotUnionError,
        match="lacks affirmative stage commitments",
    ):
        load_screening_snapshot_union(
            (first, second),
            expected_manifest_sha256=(
                _manifest_sha256(first),
                _manifest_sha256(second),
            ),
            expected_cycle_hash=_cycle_hash(tmp_path / "first"),
        )


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
    _set_firecrawl_screening_implementation(first)
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
    assert manifest["stage_commitments"]["firecrawl_screening_implementation"] == (
        firecrawl_screening_implementation()
    )
    assert (
        manifest["stage_commitments"]["screening_snapshot_union_inputs"][
            "firecrawl_screening_source_count"
        ]
        == 1
    )
    assert (
        json.loads((output_root / "screening-snapshot-union-summary.json").read_text())[
            "firecrawl_screening_source_count"
        ]
        == 1
    )
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


def test_union_of_union_uses_nested_terminal_raw_authority(tmp_path: Path) -> None:
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
                    "reason": "no_mtd_or_rule_12_reference",
                },
                b"<html><body>stale excluded proof</body></html>",
            )
        ],
    )
    corrected_evidence = _strict_screen_evidence(candidate_id)
    corrected = _snapshot(
        tmp_path / "corrected",
        batch_id="corrected-screen",
        observations=[
            (
                candidate_id,
                "accepted",
                "strict_clean_screen_passed",
                corrected_evidence,
                b"<html><body>corrected active proof</body></html>",
            )
        ],
    )
    _set_firecrawl_screening_implementation(corrected)
    cycle_hash = _cycle_hash(tmp_path / "stale")
    nested_output = tmp_path / "nested-output"
    nested_snapshot_root = tmp_path / "nested-snapshots"
    assert (
        cli_module.main(
            [
                "acquisition",
                "union-screening-snapshots",
                "--output-root",
                str(nested_output),
                "--cycle-store",
                str(tmp_path / "stale" / "cycle.sqlite3"),
                "--batch-id",
                "nested-corrected-union",
                "--expected-cycle-hash",
                cycle_hash,
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
                str(nested_snapshot_root),
                "--snapshot-id",
                "nested-complete",
                "--execute",
            ]
        )
        == 0
    )
    nested = nested_snapshot_root / "nested-complete"
    disjoint = _snapshot(
        tmp_path / "disjoint",
        batch_id="disjoint-screen",
        observations=[
            (
                "courtlistener-docket-79999999",
                "excluded",
                "strict_clean_screen_failed",
                {
                    "candidate_id": "courtlistener-docket-79999999",
                    "reason": "no_mtd_or_rule_12_reference",
                },
                b"<html><body>disjoint excluded proof</body></html>",
            )
        ],
    )

    outer = load_screening_snapshot_union(
        (nested, disjoint),
        expected_manifest_sha256=(
            _manifest_sha256(nested),
            _manifest_sha256(disjoint),
        ),
        expected_cycle_hash=cycle_hash,
    )

    assert len(outer.raw_artifacts) == 3
    active_raw = next(
        artifact
        for artifact in outer.canonical_raw_artifacts
        if artifact.candidate_id == candidate_id
    )
    assert active_raw.content == b"<html><body>corrected active proof</body></html>"
    outer_output = tmp_path / "outer-output"
    outer_snapshot_root = tmp_path / "outer-snapshots"
    assert (
        cli_module.main(
            [
                "acquisition",
                "union-screening-snapshots",
                "--output-root",
                str(outer_output),
                "--cycle-store",
                str(tmp_path / "stale" / "cycle.sqlite3"),
                "--batch-id",
                "outer-nested-union",
                "--expected-cycle-hash",
                cycle_hash,
                "--source-snapshot",
                str(nested),
                "--expected-source-snapshot-manifest-sha256",
                _manifest_sha256(nested),
                "--source-snapshot",
                str(disjoint),
                "--expected-source-snapshot-manifest-sha256",
                _manifest_sha256(disjoint),
                "--snapshot-root",
                str(outer_snapshot_root),
                "--snapshot-id",
                "outer-complete",
                "--execute",
            ]
        )
        == 0
    )
    outer_snapshot = outer_snapshot_root / "outer-complete"
    owned_records = cli_module._owned_raw_records_from_snapshot(outer_snapshot)
    active_record = next(
        record for record in owned_records if record["candidate_id"] == candidate_id
    )
    assert active_record["sha256"] == active_raw.sha256
    outer_manifest_path = outer_snapshot / "manifest.json"
    outer_manifest = json.loads(outer_manifest_path.read_text())
    nested_source = next(
        source
        for source in outer_manifest["stage_commitments"][
            "screening_snapshot_union_inputs"
        ]["sources"]
        if "screening_snapshot_union_inputs" in source["stage_commitments"]
    )
    nested_authority = next(
        row
        for row in nested_source["stage_commitments"][
            "screening_snapshot_union_inputs"
        ]["canonical_raw_artifacts"]
        if row["candidate_id"] == candidate_id
    )
    nested_authority["sha256"] = "0" * 64
    outer_manifest_path.write_text(json.dumps(outer_manifest))
    with pytest.raises(
        CycleAcquisitionStoreError,
        match="without one authenticated correction source",
    ):
        cli_module._owned_raw_records_from_snapshot(outer_snapshot)


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
    corrected_evidence = _strict_screen_evidence(candidate_id)
    # CourtListener REST strict screens can retain the numeric docket identity
    # in metadata.case_id while the owning store candidate is provider-qualified.
    corrected_evidence["candidate"]["metadata"]["case_id"] = "73330395"
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


@pytest.mark.parametrize(
    "malformed_field",
    (
        "disposition_date",
        "selected_entries",
        "motion_linkage",
        "decision_count",
    ),
)
def test_union_rejects_malformed_active_correction_evidence(
    tmp_path: Path,
    malformed_field: str,
) -> None:
    candidate_id = "courtlistener-docket-73330395"
    stale = _snapshot(
        tmp_path / f"stale-{malformed_field}",
        batch_id="baseline",
        observations=[
            (
                candidate_id,
                "excluded",
                "strict_clean_screen_failed",
                {"candidate_id": candidate_id, "reason": "procedural"},
                b"<html><body>same docket</body></html>",
            )
        ],
    )
    corrected_evidence = _strict_screen_evidence(candidate_id)
    if malformed_field == "disposition_date":
        corrected_evidence["first_written_mtd_disposition_date"] = "not-a-date"
    elif malformed_field == "selected_entries":
        corrected_evidence["selected_entries"] = [12]
    elif malformed_field == "motion_linkage":
        corrected_evidence["motion_linkage"] = {}
    else:
        corrected_evidence["mtd_decision_screen"]["actual_mtd_decision_entry_count"] = (
            True
        )
    corrected = _snapshot(
        tmp_path / f"corrected-{malformed_field}",
        batch_id="rescreen",
        observations=[
            (
                candidate_id,
                "accepted",
                "strict_clean_screen_passed",
                corrected_evidence,
                b"<html><body>same docket</body></html>",
            )
        ],
    )

    with pytest.raises(
        ScreeningSnapshotUnionError,
        match="active correction lacks an independently qualifying strict screen",
    ):
        load_screening_snapshot_union(
            (stale, corrected),
            expected_manifest_sha256=(
                _manifest_sha256(stale),
                _manifest_sha256(corrected),
            ),
            expected_cycle_hash=_cycle_hash(tmp_path / f"stale-{malformed_field}"),
            expected_terminal_correction_candidate_id=(candidate_id,),
            expected_terminal_correction_source_manifest_sha256=(
                _manifest_sha256(corrected),
            ),
        )


@pytest.mark.parametrize("terminal_state", ("accepted", "newly_free"))
def test_union_rejects_cross_candidate_strict_screen_substitution(
    tmp_path: Path,
    terminal_state: str,
) -> None:
    candidate_id = "courtlistener-docket-73330395"
    other_candidate_id = "courtlistener-docket-73330396"
    stale = _snapshot(
        tmp_path / f"stale-cross-candidate-{terminal_state}",
        batch_id="baseline",
        observations=[
            (
                candidate_id,
                "excluded",
                "strict_clean_screen_failed",
                {"candidate_id": candidate_id, "reason": "procedural"},
                b"<html><body>same docket</body></html>",
            )
        ],
    )
    substituted_evidence = _strict_screen_evidence(other_candidate_id)
    # The store already binds this top-level field. The union must also bind the
    # internally self-consistent embedded docket identity to the outer owner.
    substituted_evidence["candidate_id"] = candidate_id
    source_observations = [
        (
            candidate_id,
            "accepted",
            "strict_clean_screen_passed",
            substituted_evidence,
            b"<html><body>same docket</body></html>",
        )
    ]
    if terminal_state == "newly_free":
        source_observations.append(
            (
                candidate_id,
                "newly_free",
                "required_documents_newly_free",
                {"candidate_id": candidate_id, "document_id": "44"},
                b"<html><body>same docket</body></html>",
            )
        )
    substituted = _snapshot(
        tmp_path / f"cross-candidate-{terminal_state}",
        batch_id="rescreen",
        observations=source_observations,
    )

    with pytest.raises(
        ScreeningSnapshotUnionError,
        match="strict-screen docket ID does not match its candidate",
    ):
        load_screening_snapshot_union(
            (stale, substituted),
            expected_manifest_sha256=(
                _manifest_sha256(stale),
                _manifest_sha256(substituted),
            ),
            expected_cycle_hash=_cycle_hash(
                tmp_path / f"stale-cross-candidate-{terminal_state}"
            ),
            expected_terminal_correction_candidate_id=(candidate_id,),
            expected_terminal_correction_source_manifest_sha256=(
                _manifest_sha256(substituted),
            ),
        )


def test_strict_screen_validator_rejects_outer_candidate_substitution() -> None:
    candidate_id = "courtlistener-docket-73330395"
    evidence = _strict_screen_evidence("courtlistener-docket-73330396")

    with pytest.raises(
        StrictScreenEvidenceError,
        match="strict-screen evidence belongs to a different candidate",
    ):
        validate_strict_screen_evidence(
            evidence,
            expected_candidate_id=candidate_id,
        )


def test_strict_screen_validator_rejects_cross_case_linkage() -> None:
    candidate_id = "courtlistener-docket-73330395"
    evidence = _strict_screen_evidence(candidate_id)
    evidence["motion_linkage"]["links"][0]["case_id"] = "courtlistener-docket-73330396"

    with pytest.raises(
        StrictScreenEvidenceError,
        match="motion_linkage link case ID does not match its candidate",
    ):
        validate_strict_screen_evidence(
            evidence,
            expected_candidate_id=candidate_id,
        )


@pytest.mark.parametrize(
    "auxiliary_entry",
    (
        {
            "row_id": "entry-64",
            "entry_number": "64",
            "filed_at": "July 23, 2026",
            "text": "",
            "role": "other",
            "restriction_markers": [],
            "documents": [
                {
                    "kind": "main",
                    "description": "Judgment (Clerk's Office Only)",
                    "href": None,
                    "action_label": "Buy on PACER",
                    "pacer_only": True,
                    "freely_available": False,
                    "restriction_markers": [],
                }
            ],
        },
        {
            "row_id": "minute-entry-405945218",
            "entry_number": None,
            "filed_at": "October 23, 2024",
            "text": "",
            "role": "other",
            "restriction_markers": [],
            "documents": [
                {
                    "kind": "main",
                    "description": "Case Referred to Magistrate Judge",
                    "href": None,
                    "action_label": "Buy on PACER",
                    "pacer_only": True,
                    "freely_available": False,
                    "restriction_markers": [],
                }
            ],
        },
        {
            "row_id": "entry-1",
            "entry_number": "1",
            "filed_at": "October 22, 2025",
            "text": "",
            "role": "other",
            "restriction_markers": [],
            "documents": [
                {
                    "kind": "main",
                    "description": "Complaint",
                    "href": None,
                    "action_label": "Buy on PACER",
                    "pacer_only": True,
                    "freely_available": False,
                    "restriction_markers": [],
                }
            ],
        },
        {
            "row_id": "minute-entry-453283793",
            "entry_number": None,
            "filed_at": "February 9, 2026",
            "text": "",
            "role": "other",
            "restriction_markers": [],
            "documents": [
                {
                    "kind": "main",
                    "description": "Motion for Leave to File Sealed Document",
                    "href": None,
                    "action_label": "Buy on PACER",
                    "pacer_only": True,
                    "freely_available": False,
                    "restriction_markers": ["text_sealeddocument"],
                }
            ],
        },
    ),
)
def test_strict_screen_validator_accepts_described_blank_auxiliary_rest_rows(
    auxiliary_entry: dict[str, object],
) -> None:
    candidate_id = "courtlistener-docket-73330395"
    evidence = _strict_screen_evidence(candidate_id)
    evidence["selected_entries"].append(auxiliary_entry)

    validate_strict_screen_evidence(
        evidence,
        expected_candidate_id=candidate_id,
    )


def test_strict_screen_validator_rejects_blank_target_motion_text() -> None:
    candidate_id = "courtlistener-docket-73330395"
    evidence = _strict_screen_evidence(candidate_id)
    evidence["selected_entries"][0]["text"] = ""
    evidence["selected_entries"][0]["role"] = "other"

    with pytest.raises(
        StrictScreenEvidenceError,
        match=r"selected_entries\[1\]\.text must be a non-empty string",
    ):
        validate_strict_screen_evidence(
            evidence,
            expected_candidate_id=candidate_id,
        )


def test_strict_screen_validator_rejects_blank_substantive_role_text() -> None:
    candidate_id = "courtlistener-docket-73330395"
    evidence = _strict_screen_evidence(candidate_id)
    evidence["selected_entries"].append(
        {
            "row_id": "entry-8",
            "entry_number": "8",
            "filed_at": "February 10, 2026",
            "text": "",
            "role": "opposition",
            "restriction_markers": [],
            "documents": [
                {
                    "kind": "main",
                    "description": "Opposition to Motion to Dismiss",
                    "href": None,
                    "action_label": "Buy on PACER",
                    "pacer_only": True,
                    "freely_available": False,
                    "restriction_markers": [],
                }
            ],
        }
    )

    with pytest.raises(
        StrictScreenEvidenceError,
        match=r"selected_entries\[3\]\.text must be a non-empty string",
    ):
        validate_strict_screen_evidence(
            evidence,
            expected_candidate_id=candidate_id,
        )


def test_strict_screen_validator_rejects_blank_decision_text() -> None:
    candidate_id = "courtlistener-docket-73330395"
    evidence = _strict_screen_evidence(candidate_id)
    evidence["selected_entries"][1]["text"] = ""
    evidence["selected_entries"][1]["role"] = "other"

    with pytest.raises(
        StrictScreenEvidenceError,
        match=r"selected_entries\[2\]\.text must be a non-empty string",
    ):
        validate_strict_screen_evidence(
            evidence,
            expected_candidate_id=candidate_id,
        )


def test_strict_screen_validator_rejects_undescribed_blank_auxiliary_row() -> None:
    candidate_id = "courtlistener-docket-73330395"
    evidence = _strict_screen_evidence(candidate_id)
    evidence["selected_entries"].append(
        {
            "row_id": "minute-entry-405945218",
            "entry_number": None,
            "filed_at": "October 23, 2024",
            "text": "",
            "role": "other",
            "restriction_markers": [],
            "documents": [
                {
                    "kind": "main",
                    "description": "",
                    "href": None,
                    "action_label": "Buy on PACER",
                    "pacer_only": True,
                    "freely_available": False,
                    "restriction_markers": [],
                }
            ],
        }
    )

    with pytest.raises(
        StrictScreenEvidenceError,
        match=r"selected_entries\[3\]\.text must be a non-empty string",
    ):
        validate_strict_screen_evidence(
            evidence,
            expected_candidate_id=candidate_id,
        )


def test_strict_screen_validator_rejects_linked_blank_auxiliary_row() -> None:
    candidate_id = "courtlistener-docket-73330395"
    evidence = _strict_screen_evidence(candidate_id)
    evidence["selected_entries"].append(
        {
            "row_id": "entry-64",
            "entry_number": "64",
            "filed_at": "July 23, 2026",
            "text": "",
            "role": "other",
            "restriction_markers": [],
            "documents": [
                {
                    "kind": "main",
                    "description": "Judgment (Clerk's Office Only)",
                    "href": None,
                    "action_label": "Buy on PACER",
                    "pacer_only": True,
                    "freely_available": False,
                    "restriction_markers": [],
                }
            ],
        }
    )
    evidence["motion_linkage"]["links"][0]["motion_entry_ids"].append("entry-64")

    with pytest.raises(
        StrictScreenEvidenceError,
        match="motion_linkage references a blank auxiliary row",
    ):
        validate_strict_screen_evidence(
            evidence,
            expected_candidate_id=candidate_id,
        )


def test_union_authenticates_newly_free_correction_from_prior_strict_screen(
    tmp_path: Path,
) -> None:
    candidate_id = "courtlistener-docket-73330395"
    stale = _snapshot(
        tmp_path / "stale-newly-free",
        batch_id="baseline",
        observations=[
            (
                candidate_id,
                "excluded",
                "strict_clean_screen_failed",
                {"candidate_id": candidate_id, "reason": "procedural"},
                b"<html><body>same docket</body></html>",
            )
        ],
    )
    newly_free = _snapshot(
        tmp_path / "newly-free",
        batch_id="availability-refresh",
        observations=[
            (
                candidate_id,
                "accepted",
                "strict_clean_screen_passed",
                _strict_screen_evidence(candidate_id),
                b"<html><body>same docket</body></html>",
            ),
            (
                candidate_id,
                "newly_free",
                "required_documents_newly_free",
                {"candidate_id": candidate_id, "document_id": "44"},
                b"<html><body>same docket</body></html>",
            ),
        ],
    )

    union = load_screening_snapshot_union(
        (stale, newly_free),
        expected_manifest_sha256=(
            _manifest_sha256(stale),
            _manifest_sha256(newly_free),
        ),
        expected_cycle_hash=_cycle_hash(tmp_path / "stale-newly-free"),
        expected_terminal_correction_candidate_id=(candidate_id,),
        expected_terminal_correction_source_manifest_sha256=(
            _manifest_sha256(newly_free),
        ),
    )

    [candidate] = union.candidates
    assert candidate.state == "newly_free"
    assert candidate.reason_code == "required_documents_newly_free"


def test_union_command_archives_and_resumes_authenticated_terminal_correction(
    tmp_path: Path,
) -> None:
    candidate_id = "courtlistener-docket-73330395"
    stale_root = tmp_path / "stale"
    corrected_root = tmp_path / "corrected"
    selected_entries = [
        _embedded_entry(
            1,
            "COMPLAINT filed by Plaintiff.",
            "Complaint",
            "https://storage.courtlistener.com/complaint.pdf",
            role="other",
            pacer_only=False,
        ),
        _embedded_entry(
            5,
            "MOTION to Dismiss filed by Defendant.",
            "Motion to Dismiss",
            "https://ecf.nysd.uscourts.gov/doc1/12345",
            role="mtd_notice",
            pacer_only=True,
        ),
        _embedded_entry(
            12,
            "ORDER on Motion to Dismiss.",
            "Order on Motion to Dismiss",
            "https://storage.courtlistener.com/decision.pdf",
            role="decision",
            pacer_only=False,
        ),
    ]
    docket_html = _raw_docket_html(selected_entries)
    stale = _snapshot(
        stale_root,
        batch_id="baseline",
        observations=[
            (
                candidate_id,
                "excluded",
                "strict_clean_screen_failed",
                {"candidate_id": candidate_id, "reason": "procedural"},
                docket_html,
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
                _strict_screen_evidence(
                    candidate_id,
                    selected_entries=selected_entries,
                ),
                docket_html,
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
    raw_bindings = [row["raw_artifacts"][0] for row in archived]
    assert {binding["retrieved_at"] for binding in raw_bindings} == {
        "2026-07-16T12:00:00Z"
    }
    assert {binding["source_retrieved_at"] for binding in raw_bindings} == {
        "2026-07-16T12:00:00Z",
        "2026-07-16T13:00:00Z",
    }
    [packet_raw] = _jsonl(output_root / "union-raw-artifacts.jsonl")
    assert packet_raw["sha256"] == hashlib.sha256(docket_html).hexdigest()
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
    assert raw_paths["73330395"].read_bytes() == docket_html

    (output_root / "union-terminal-observations.jsonl").write_text("")
    assert cli_module.main(command) == 0
    assert _jsonl(output_root / "union-terminal-observations.jsonl") == archived

    assert (
        cli_module.main(
            [
                "acquisition",
                "plan-public-downloads",
                "--output-root",
                str(tmp_path / "public-plan"),
                "--snapshot",
                str(snapshot),
                "--expected-cycle-hash",
                _cycle_hash(stale_root),
                "--raw-html-dir",
                str(output_root / "union-raw-artifacts"),
                "--use-embedded-entries",
                "--target-clean-cases",
                "1",
                "--cost-per-missing-document-usd",
                "0.10",
                "--execute",
            ]
        )
        == 0
    )

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
    original_manifest = manifest_path.read_text()
    manifest = json.loads(original_manifest)
    correction = manifest["stage_commitments"]["screening_snapshot_union_inputs"][
        "longitudinal_corrections"
    ][0]
    forged_source_hash = "f" * 64
    authoritative_source_hash = correction["canonical_source_manifest_sha256"]
    correction["canonical_source_manifest_sha256"] = forged_source_hash
    authoritative_observation = next(
        observation
        for observation in correction["observations"]
        if observation["source_manifest_sha256"] == authoritative_source_hash
    )
    authoritative_observation["source_manifest_sha256"] = forged_source_hash
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(CycleAcquisitionStoreError, match="unauthenticated authority"):
        cli_module._owned_raw_records_from_snapshot(snapshot)

    manifest = json.loads(original_manifest)
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
                _strict_screen_evidence(candidate_id),
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


def test_union_allows_raw_backed_active_authority_over_exact310_rawless_reproof(
    tmp_path: Path,
) -> None:
    candidate_id = "courtlistener-docket-72615251"
    raw_backed_evidence = _strict_screen_evidence(candidate_id)
    raw_backed = _snapshot(
        tmp_path / "raw-backed",
        batch_id="terminal-screen",
        observations=[
            (
                candidate_id,
                "accepted",
                "strict_clean_screen_passed",
                raw_backed_evidence,
                b"<html><body>authenticated docket proof</body></html>",
            )
        ],
    )
    reproof_evidence = deepcopy(raw_backed_evidence)
    reproof_evidence["policy_rebind"] = {
        "strategy": "authenticated_strict_evidence_reproof_v1",
        "current_policy_proof_available": True,
        "raw_artifact_count": 0,
        "source_cycle_hash": "a" * 64,
        "source_batch_id": "exact310-source",
        "source_snapshot_manifest_sha256": "b" * 64,
        "source_observation_sha256": "c" * 64,
        "source_state": "accepted",
        "source_reason_code": "strict_clean_screen_passed",
        "target_cycle_hash": _cycle_hash(tmp_path / "raw-backed"),
    }
    rawless_reproof = _snapshot(
        tmp_path / "rawless-reproof",
        batch_id="exact310-rebind",
        observations=[
            (
                candidate_id,
                "accepted",
                "strict_clean_screen_passed",
                reproof_evidence,
                b"<html><body>temporary helper bytes</body></html>",
            )
        ],
    )
    _rewrite_snapshot_jsonl(rawless_reproof, "raw-artifacts.jsonl", [])

    with pytest.raises(
        ScreeningSnapshotUnionError,
        match="multiple non-identical active terminal proofs",
    ):
        load_screening_snapshot_union(
            (raw_backed, rawless_reproof),
            expected_manifest_sha256=(
                _manifest_sha256(raw_backed),
                _manifest_sha256(rawless_reproof),
            ),
            expected_cycle_hash=_cycle_hash(tmp_path / "raw-backed"),
            expected_terminal_correction_candidate_id=(candidate_id,),
            expected_terminal_correction_source_manifest_sha256=(
                _manifest_sha256(raw_backed),
            ),
        )

    _set_exact310_stage_commitments(
        rawless_reproof,
        policy_rebind=reproof_evidence["policy_rebind"],
    )
    union = load_screening_snapshot_union(
        (raw_backed, rawless_reproof),
        expected_manifest_sha256=(
            _manifest_sha256(raw_backed),
            _manifest_sha256(rawless_reproof),
        ),
        expected_cycle_hash=_cycle_hash(tmp_path / "raw-backed"),
        expected_terminal_correction_candidate_id=(candidate_id,),
        expected_terminal_correction_source_manifest_sha256=(
            _manifest_sha256(raw_backed),
        ),
    )

    [candidate] = union.candidates
    assert candidate.evidence == raw_backed_evidence
    [canonical_raw] = union.canonical_raw_artifacts
    assert canonical_raw.content == (
        b"<html><body>authenticated docket proof</body></html>"
    )
    [correction] = union.stage_commitment["longitudinal_corrections"]
    assert correction["active_reproof_reconciliation"] == {
        "policy": (
            "unique_raw_backed_authority_over_authenticated_rawless_exact310_reproof_v1"
        ),
        "rawless_source_manifest_sha256": [
            _manifest_sha256(rawless_reproof),
        ],
    }
    assert cli_module._snapshot_longitudinal_active_raw_mapping(
        union.stage_commitment,
        candidate_records=[
            {
                "candidate_id": candidate.candidate_id,
                "state": candidate.state,
                "reason_code": candidate.reason_code,
                "evidence": candidate.evidence,
            }
        ],
        archived_records=[
            {
                "candidate_id": artifact.candidate_id,
                "sha256": artifact.sha256,
                "byte_count": artifact.byte_count,
                "retrieved_at": artifact.retrieved_at,
            }
            for artifact in union.raw_artifacts
        ],
    ) == {
        candidate_id: (
            canonical_raw.sha256,
            canonical_raw.byte_count,
            canonical_raw.retrieved_at,
        )
    }
    tampered_commitment = deepcopy(union.stage_commitment)
    del tampered_commitment["longitudinal_corrections"][0][
        "active_reproof_reconciliation"
    ]
    with pytest.raises(
        CycleAcquisitionStoreError,
        match="not uniquely reconcilable",
    ):
        cli_module._snapshot_longitudinal_active_raw_mapping(
            tampered_commitment,
            candidate_records=[
                {
                    "candidate_id": candidate.candidate_id,
                    "state": candidate.state,
                    "reason_code": candidate.reason_code,
                    "evidence": candidate.evidence,
                }
            ],
            archived_records=[
                {
                    "candidate_id": artifact.candidate_id,
                    "sha256": artifact.sha256,
                    "byte_count": artifact.byte_count,
                    "retrieved_at": artifact.retrieved_at,
                }
                for artifact in union.raw_artifacts
            ],
        )

    tampered_commitment = deepcopy(union.stage_commitment)
    rawless_source = next(
        source
        for source in tampered_commitment["sources"]
        if source["manifest_sha256"] == _manifest_sha256(rawless_reproof)
    )
    rawless_source["stage_commitments"]["target_cycle_hash"] = "d" * 64
    with pytest.raises(
        CycleAcquisitionStoreError,
        match="invalid rawless active reproof",
    ):
        cli_module._snapshot_longitudinal_active_raw_mapping(
            tampered_commitment,
            candidate_records=[
                {
                    "candidate_id": candidate.candidate_id,
                    "state": candidate.state,
                    "reason_code": candidate.reason_code,
                    "evidence": candidate.evidence,
                }
            ],
            archived_records=[
                {
                    "candidate_id": artifact.candidate_id,
                    "sha256": artifact.sha256,
                    "byte_count": artifact.byte_count,
                    "retrieved_at": artifact.retrieved_at,
                }
                for artifact in union.raw_artifacts
            ],
        )

    newly_free_reproof = _snapshot(
        tmp_path / "newly-free-reproof",
        batch_id="exact310-newly-free",
        observations=[
            (
                candidate_id,
                "newly_free",
                "newly_free",
                reproof_evidence,
                b"<html><body>temporary helper bytes</body></html>",
            )
        ],
    )
    _rewrite_snapshot_jsonl(newly_free_reproof, "raw-artifacts.jsonl", [])
    _set_exact310_stage_commitments(
        newly_free_reproof,
        policy_rebind=reproof_evidence["policy_rebind"],
    )
    with pytest.raises(
        ScreeningSnapshotUnionError,
        match="multiple non-identical active terminal proofs",
    ):
        load_screening_snapshot_union(
            (raw_backed, newly_free_reproof),
            expected_manifest_sha256=(
                _manifest_sha256(raw_backed),
                _manifest_sha256(newly_free_reproof),
            ),
            expected_cycle_hash=_cycle_hash(tmp_path / "raw-backed"),
            expected_terminal_correction_candidate_id=(candidate_id,),
            expected_terminal_correction_source_manifest_sha256=(
                _manifest_sha256(raw_backed),
            ),
        )


def test_union_rejects_generic_rawless_distinct_active_proof(
    tmp_path: Path,
) -> None:
    candidate_id = "courtlistener-docket-72615251"
    raw_backed_evidence = _strict_screen_evidence(candidate_id)
    raw_backed = _snapshot(
        tmp_path / "raw-backed",
        batch_id="terminal-screen",
        observations=[
            (
                candidate_id,
                "accepted",
                "strict_clean_screen_passed",
                raw_backed_evidence,
                b"<html><body>authenticated docket proof</body></html>",
            )
        ],
    )
    rawless_evidence = deepcopy(raw_backed_evidence)
    rawless_evidence["candidate"]["url"] = (
        "https://www.courtlistener.com/docket/72615251/other-proof/"
    )
    rawless = _snapshot(
        tmp_path / "rawless",
        batch_id="unbound-rescreen",
        observations=[
            (
                candidate_id,
                "accepted",
                "strict_clean_screen_passed",
                rawless_evidence,
                b"<html><body>temporary helper bytes</body></html>",
            )
        ],
    )
    _rewrite_snapshot_jsonl(rawless, "raw-artifacts.jsonl", [])

    with pytest.raises(
        ScreeningSnapshotUnionError,
        match="multiple non-identical active terminal proofs",
    ):
        load_screening_snapshot_union(
            (raw_backed, rawless),
            expected_manifest_sha256=(
                _manifest_sha256(raw_backed),
                _manifest_sha256(rawless),
            ),
            expected_cycle_hash=_cycle_hash(tmp_path / "raw-backed"),
            expected_terminal_correction_candidate_id=(candidate_id,),
            expected_terminal_correction_source_manifest_sha256=(
                _manifest_sha256(raw_backed),
            ),
        )


def test_union_allows_raw_backed_authority_over_authenticated_direct_rest_proof(
    tmp_path: Path,
) -> None:
    candidate_id = "courtlistener-docket-61568804"
    raw_backed_evidence = _strict_screen_evidence(candidate_id)
    raw_backed = _snapshot(
        tmp_path / "raw-backed",
        batch_id="firecrawl-screen",
        observations=[
            (
                candidate_id,
                "accepted",
                "strict_clean_screen_passed",
                raw_backed_evidence,
                b"<html><body>current public docket proof</body></html>",
            )
        ],
    )
    _set_firecrawl_screening_implementation(raw_backed)

    direct_rest_evidence = deepcopy(raw_backed_evidence)
    direct_rest_evidence["candidate"]["url"] = (
        "https://www.courtlistener.com/docket/61568804/rest-observation/"
    )
    direct_rest = _snapshot(
        tmp_path / "direct-rest",
        batch_id="direct-rest-screen",
        observations=[
            (
                candidate_id,
                "accepted",
                "strict_clean_screen_passed",
                direct_rest_evidence,
                b"<html><body>temporary helper bytes</body></html>",
            )
        ],
    )
    _rewrite_snapshot_jsonl(direct_rest, "raw-artifacts.jsonl", [])

    union = load_screening_snapshot_union(
        (raw_backed, direct_rest),
        expected_manifest_sha256=(
            _manifest_sha256(raw_backed),
            _manifest_sha256(direct_rest),
        ),
        expected_cycle_hash=_cycle_hash(tmp_path / "raw-backed"),
        expected_terminal_correction_candidate_id=(candidate_id,),
        expected_terminal_correction_source_manifest_sha256=(
            _manifest_sha256(raw_backed),
        ),
    )

    [candidate] = union.candidates
    assert candidate.evidence == raw_backed_evidence
    [canonical_raw] = union.canonical_raw_artifacts
    assert canonical_raw.content == (
        b"<html><body>current public docket proof</body></html>"
    )
    [correction] = union.stage_commitment["longitudinal_corrections"]
    assert correction["active_reproof_reconciliation"] == {
        "policy": (
            "unique_raw_backed_authority_over_authenticated_rawless_"
            "direct_rest_proof_v1"
        ),
        "rawless_source_manifest_sha256": [
            _manifest_sha256(direct_rest),
        ],
    }
    candidate_records = [
        {
            "candidate_id": candidate.candidate_id,
            "state": candidate.state,
            "reason_code": candidate.reason_code,
            "evidence": candidate.evidence,
        }
    ]
    archived_records = [
        {
            "candidate_id": artifact.candidate_id,
            "sha256": artifact.sha256,
            "byte_count": artifact.byte_count,
            "retrieved_at": artifact.retrieved_at,
        }
        for artifact in union.raw_artifacts
    ]
    assert cli_module._snapshot_longitudinal_active_raw_mapping(
        union.stage_commitment,
        candidate_records=candidate_records,
        archived_records=archived_records,
    ) == {
        candidate_id: (
            canonical_raw.sha256,
            canonical_raw.byte_count,
            canonical_raw.retrieved_at,
        )
    }

    tampered_commitment = deepcopy(union.stage_commitment)
    rawless_source = next(
        source
        for source in tampered_commitment["sources"]
        if source["manifest_sha256"] == _manifest_sha256(direct_rest)
    )
    rawless_source["stage_commitments"]["unbound"] = True
    with pytest.raises(
        CycleAcquisitionStoreError,
        match="invalid rawless active reproof",
    ):
        cli_module._snapshot_longitudinal_active_raw_mapping(
            tampered_commitment,
            candidate_records=candidate_records,
            archived_records=archived_records,
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
                _strict_screen_evidence(candidate_id),
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
    active_evidence = _strict_screen_evidence(candidate_id)
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


def test_union_consumes_pinned_manifest_buffer_when_path_is_replaced(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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
                {"candidate_id": candidate_id, "reason": "no_mtd_reference"},
                b"<html><body>baseline docket</body></html>",
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
                {"candidate_id": candidate_id, "reason": "no_mtd_reference"},
                b"<html><body>terminal docket</body></html>",
            )
        ],
    )
    first_manifest_sha256 = _manifest_sha256(first)
    first_manifest_path = first / "manifest.json"
    replacement = json.loads(first_manifest_path.read_text())
    replacement["batch_id"] = "replacement-must-not-propagate"
    replacement_payload = json.dumps(replacement).encode()
    original_read = union_module._read_regular_file
    replaced = False

    def replace_after_buffer(path: Path, label: str) -> bytes:
        nonlocal replaced
        payload = original_read(path, label)
        if path == first_manifest_path and not replaced:
            first_manifest_path.write_bytes(replacement_payload)
            replaced = True
        return payload

    monkeypatch.setattr(union_module, "_read_regular_file", replace_after_buffer)

    union = load_screening_snapshot_union(
        (first, second),
        expected_manifest_sha256=(
            first_manifest_sha256,
            _manifest_sha256(second),
        ),
        expected_cycle_hash=_cycle_hash(tmp_path / "first"),
    )

    assert replaced is True
    assert union.stage_commitment["sources"][0]["batch_id"] == "baseline"


def test_union_consumes_authenticated_payload_buffer_when_path_mutates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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
                {"candidate_id": candidate_id, "reason": "no_mtd_reference"},
                b"<html><body>baseline docket</body></html>",
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
                {"candidate_id": candidate_id, "reason": "no_mtd_reference"},
                b"<html><body>terminal docket</body></html>",
            )
        ],
    )
    candidates_path = first / "candidates.jsonl"
    [replacement] = _jsonl(candidates_path)
    replacement["reason_code"] = "tampered_after_authentication"
    replacement["evidence"] = {
        "candidate_id": candidate_id,
        "reason": "tampered_after_authentication",
    }
    replacement_payload = (json.dumps(replacement) + "\n").encode()
    original_read = union_module._read_regular_file
    mutated = False

    def mutate_after_buffer(path: Path, label: str) -> bytes:
        nonlocal mutated
        payload = original_read(path, label)
        if path == candidates_path and not mutated:
            candidates_path.write_bytes(replacement_payload)
            mutated = True
        return payload

    monkeypatch.setattr(union_module, "_read_regular_file", mutate_after_buffer)

    union = load_screening_snapshot_union(
        (first, second),
        expected_manifest_sha256=(
            _manifest_sha256(first),
            _manifest_sha256(second),
        ),
        expected_cycle_hash=_cycle_hash(tmp_path / "first"),
    )

    assert mutated is True
    assert union.candidates[0].reason_code == "strict_clean_screen_failed"


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
                for candidate_id in dict.fromkeys(
                    candidate_id
                    for (
                        candidate_id,
                        _state,
                        _reason,
                        _evidence,
                        _content,
                    ) in observations
                )
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
            stage_commitments={
                "courtlistener_rest_screen_inputs": {
                    "schema_version": (
                        "legalforecast.courtlistener_rest_screen_inputs.v1"
                    )
                }
            },
        )


def _embedded_entry(
    number: int,
    text: str,
    description: str,
    href: str,
    *,
    role: str,
    pacer_only: bool,
) -> dict[str, object]:
    return {
        "row_id": f"entry-{number}",
        "entry_number": str(number),
        "filed_at": "2026-06-30",
        "text": text,
        "role": role,
        "restriction_markers": [],
        "documents": [
            {
                "kind": "Main Document",
                "description": description,
                "href": href,
                "action_label": "Buy on PACER" if pacer_only else "Download PDF",
                "pacer_only": pacer_only,
                "freely_available": not pacer_only,
                "restriction_markers": [],
            }
        ],
    }


def _strict_screen_evidence(
    candidate_id: str,
    *,
    selected_entries: list[dict[str, object]] | None = None,
) -> dict[str, Any]:
    docket_id = candidate_id.removeprefix("courtlistener-docket-")
    entries = selected_entries or [
        _embedded_entry(
            5,
            "MOTION to Dismiss filed by Defendant.",
            "Motion to Dismiss",
            "https://ecf.nysd.uscourts.gov/doc1/12345",
            role="mtd_notice",
            pacer_only=True,
        ),
        _embedded_entry(
            12,
            "ORDER on Motion to Dismiss.",
            "Order on Motion to Dismiss",
            "https://storage.courtlistener.com/decision.pdf",
            role="decision",
            pacer_only=False,
        ),
    ]
    return {
        "candidate_id": candidate_id,
        "candidate": {
            "docket_id": docket_id,
            "candidate_key": docket_id,
            "metadata": {
                "case_id": candidate_id,
                "case_name": "Fixture v. Example",
                "court": "nysd",
                "docket_number": "1:26-cv-00001",
            },
            "url": f"https://www.courtlistener.com/docket/{docket_id}/fixture/",
        },
        "ai": {
            "target_motion_entry_numbers": ["5"],
            "decision_entry_numbers": ["12"],
        },
        "first_written_mtd_disposition_date": "2026-06-30",
        "eligibility_anchor_date": "2026-06-30",
        "selected_entries": entries,
        "mtd_decision_screen": {
            "status": "accepted_strict_civil_mtd_decision",
            "exclusion_reasons": [],
            "actual_mtd_decision_entry_count": 1,
            "decision_entries": [
                {
                    "row_id": "entry-12",
                    "entry_number": "12",
                    "filed_at": "2026-06-30",
                    "actual_mtd_decision": True,
                    "exclusion_reasons": [],
                }
            ],
        },
        "motion_linkage": {
            "candidate_id": docket_id,
            "case_id": candidate_id,
            "is_clean": True,
            "links": [
                {
                    "candidate_id": docket_id,
                    "case_id": candidate_id,
                    "motion_entry_ids": ["entry-5"],
                    "disposition_entry_ids": ["entry-12"],
                    "linkage_basis": ["fixture"],
                }
            ],
            "exclusion_entries": [],
        },
    }


def _raw_docket_html(entries: list[dict[str, object]]) -> bytes:
    rows: list[str] = []
    for entry in entries:
        [document] = entry["documents"]  # type: ignore[misc]
        rows.append(
            '<div class="row" id="{row_id}">'
            '<div class="col-xs-1">{entry_number}</div>'
            '<div class="col-xs-3"><span title="{filed_at}">{filed_at}</span>'
            "</div>"
            '<div class="col-xs-8">{text}'
            '<div class="recap-documents"><div>{kind}</div>'
            "<div>{description}</div>"
            '<a href="{href}">{action_label}</a>'
            "</div></div></div>".format(
                row_id=entry["row_id"],
                entry_number=entry["entry_number"],
                filed_at=entry["filed_at"],
                text=entry["text"],
                kind=document["kind"],
                description=document["description"],
                href=document["href"],
                action_label=document["action_label"],
            )
        )
    return (
        "<html><head><title>Fixture docket</title></head><body>"
        '<div id="docket-entry-table">' + "".join(rows) + "</div></body></html>"
    ).encode()


def _manifest_sha256(snapshot: Path) -> str:
    return hashlib.sha256((snapshot / "manifest.json").read_bytes()).hexdigest()


def _set_firecrawl_screening_implementation(snapshot: Path) -> None:
    manifest_path = snapshot / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    stage_commitments = manifest.setdefault("stage_commitments", {})
    stage_commitments["firecrawl_screen_inputs"] = {
        "schema_version": "legalforecast.firecrawl_screen_input_commitment.v1"
    }
    stage_commitments["firecrawl_screening_implementation"] = (
        firecrawl_screening_implementation()
    )
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    )


def _set_exact310_stage_commitments(
    snapshot: Path,
    *,
    policy_rebind: dict[str, Any],
) -> None:
    manifest_path = snapshot / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    candidate_count = manifest["files"]["candidates.jsonl"]["row_count"]
    manifest["stage_commitments"] = {
        "stage": "exact310-terminal-rest-policy-rebind",
        "contract_sha256": "d" * 64,
        "source_cycle_hash": policy_rebind["source_cycle_hash"],
        "source_batch_id": policy_rebind["source_batch_id"],
        "source_snapshot_manifest_sha256": policy_rebind[
            "source_snapshot_manifest_sha256"
        ],
        "source_candidate_set_sha256": "e" * 64,
        "transfer_receipt_sha256": "f" * 64,
        "target_seed_summary_sha256": "1" * 64,
        "source_observations_sha256": "2" * 64,
        "target_cycle_hash": policy_rebind["target_cycle_hash"],
        "target_batch_id": manifest["batch_id"],
        "target_batch_digest": manifest["batch_digest"],
        "target_outcomes_sha256": "3" * 64,
        "preserve_current_count": 0,
        "reprove_current_count": candidate_count,
        "reprove_exclusion_count": 0,
        "fail_closed_count": 0,
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
    }
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    )


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
