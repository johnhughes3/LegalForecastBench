"""CLI coverage for provider-free opinion docket-gap planning."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import legalforecast.cli as cli
import pytest
from pytest import CaptureFixture, MonkeyPatch


def _gap() -> dict[str, object]:
    return {
        "candidate_id": "courtlistener-docket-555",
        "docket_id": "555",
        "reason_code": "opinion_backed_docket_history_incomplete",
        "reason": "opinion_backed_docket_history_incomplete",
        "primary_exclusion_reason": "opinion_backed_docket_history_incomplete",
        "paid_gap_candidate": True,
        "packet_eligible": False,
        "planning_status": "docket_history_recovery_required",
        "opinion_source_binding_verified": True,
        "source_batch_complete_saturated": True,
        "target_motion_linkage_proven": False,
        "earliest_written_disposition_proven": False,
        "eligibility_anchor": "2026-06-30",
        "decision_window_end": "2026-07-15",
        "reconstruction_proof": {
            "docket_id": "555",
            "entry_count": 0,
            "cursor_exhausted": True,
            "complete": True,
        },
        "opinion_disposition_evidence": {
            "schema_version": "legalforecast.validated_public_opinion.v1",
            "source_opinion_docket_id": "73614335",
            "cluster_id": "10927691",
            "opinion_id": "11395231",
            "opinion_date": "2026-07-14",
            "public_pdf_url": (
                "https://storage.courtlistener.com/pdf/2026/07/14/example.pdf"
            ),
            "plain_text_sha256": "a" * 64,
            "disposition_excerpt": "The motion to dismiss is denied.",
            "cluster_response_sha256": "b" * 64,
            "opinion_response_sha256": "c" * 64,
        },
    }


def test_plan_opinion_docket_gaps_help_is_explicitly_nonexecuting(
    capsys: CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["acquisition", "plan-opinion-docket-gaps", "--help"])
    assert exit_info.value.code == 0

    output = capsys.readouterr().out
    assert "provider-free" in output
    assert "cannot select documents" in output
    assert "--cost-per-docket-usd" in output


def test_plan_opinion_docket_gaps_rejects_invalid_decimal_argument(
    capsys: CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main(
            [
                "acquisition",
                "plan-opinion-docket-gaps",
                "--output-root",
                "unused",
                "--snapshot",
                "unused-snapshot",
                "--expected-cycle-hash",
                "d" * 64,
                "--expected-snapshot-manifest-sha256",
                "e" * 64,
                "--cost-per-docket-usd",
                "not-a-decimal",
            ]
        )
    assert exit_info.value.code == 2
    assert "must be a decimal" in capsys.readouterr().err


def test_plan_opinion_docket_gaps_writes_verified_projection(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    (snapshot / "manifest.json").write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(
        cli,
        "_validate_external_snapshot_manifest_pin",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        cli,
        "load_verified_screening_snapshot",
        lambda *_args, **_kwargs: SimpleNamespace(
            exclusions=(_gap(),),
            manifest_sha256="e" * 64,
            manifest={
                "cycle_hash": "d" * 64,
                "batch_id": "cycle1-opinion-gap-source-v1",
                "batch_digest": "f" * 64,
                "files": {"exclusions.jsonl": {"sha256": "1" * 64}},
            },
        ),
    )
    output_root = tmp_path / "out"

    assert (
        cli.main(
            [
                "acquisition",
                "plan-opinion-docket-gaps",
                "--output-root",
                str(output_root),
                "--snapshot",
                str(snapshot),
                "--expected-cycle-hash",
                "d" * 64,
                "--expected-snapshot-manifest-sha256",
                "e" * 64,
                "--cost-per-docket-usd",
                "3.05",
                "--execute",
            ]
        )
        == 0
    )

    [item] = [
        json.loads(line)
        for line in (output_root / "opinion-docket-gap-plan.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    summary = json.loads(
        (output_root / "opinion-docket-gap-plan-summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert item["refresh_scope"] == "docket_history_only"
    assert item["packet_eligible"] is False
    assert summary["candidate_count"] == 1
    assert summary["total_projected_cost_usd"] == "3.05"
    assert summary["paid_activity_requested"] is False
    assert summary["source_manifest_sha256"] == "e" * 64
    assert summary["source_cycle_hash"] == "d" * 64
    assert summary["source_exclusions_sha256"] == "1" * 64
    assert "items" not in summary
    assert json.loads(capsys.readouterr().out)["plan_sha256"] == summary["plan_sha256"]


def test_plan_opinion_docket_gaps_rejects_output_aliases_and_snapshot_writes(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    manifest = snapshot / "manifest.json"
    manifest.write_text("{}\n", encoding="utf-8")
    output_root = tmp_path / "out"
    shared = output_root / "shared.json"
    common = [
        "acquisition",
        "plan-opinion-docket-gaps",
        "--output-root",
        str(output_root),
        "--snapshot",
        str(snapshot),
        "--expected-cycle-hash",
        "d" * 64,
        "--expected-snapshot-manifest-sha256",
        "e" * 64,
        "--cost-per-docket-usd",
        "3.05",
        "--execute",
    ]

    assert (
        cli.main(
            [*common, "--plan-output", str(shared), "--summary-output", str(shared)]
        )
        == 2
    )
    assert "outputs must be distinct" in capsys.readouterr().err

    assert cli.main([*common, "--plan-output", str(manifest)]) == 2
    assert "outside the immutable snapshot" in capsys.readouterr().err
    assert manifest.read_text(encoding="utf-8") == "{}\n"

    nested = snapshot / "raw" / "evidence.json"
    nested.parent.mkdir()
    nested.write_text("{}\n", encoding="utf-8")
    alias = output_root / "nested-source-alias.json"
    alias.parent.mkdir(parents=True, exist_ok=True)
    alias.hardlink_to(nested)
    assert cli.main([*common, "--plan-output", str(alias)]) == 2
    assert "aliases immutable snapshot evidence" in capsys.readouterr().err


def test_plan_opinion_docket_gaps_records_invalid_manifest_pin_failure(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    (snapshot / "manifest.json").write_text("{}\n", encoding="utf-8")
    output_root = tmp_path / "out"

    assert (
        cli.main(
            [
                "acquisition",
                "plan-opinion-docket-gaps",
                "--output-root",
                str(output_root),
                "--snapshot",
                str(snapshot),
                "--expected-cycle-hash",
                "d" * 64,
                "--expected-snapshot-manifest-sha256",
                "invalid",
                "--cost-per-docket-usd",
                "3.05",
            ]
        )
        == 2
    )
    assert "expected snapshot manifest SHA-256" in capsys.readouterr().err
    run_card = json.loads(
        (output_root / "run-cards" / "plan-opinion-docket-gaps.json").read_text(
            encoding="utf-8"
        )
    )
    assert run_card["status"] == "failed"
    assert run_card["paid_activity_requested"] is False
