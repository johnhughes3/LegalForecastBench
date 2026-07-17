from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from legalforecast.cli import build_parser, main
from legalforecast.selection.candidate_discovery import mtd_discovery_search_terms
from tests.test_static_result_sites import write_official_report_fixture


def test_cli_help_lists_benchmark_orchestration_commands() -> None:
    help_text = build_parser().format_help()

    for command in (
        "discover",
        "retrieve",
        "case-dev-smoke",
        "extract",
        "link",
        "unitize",
        "label",
        "packet",
        "packet-build",
        "eval",
        "model-run",
        "score",
        "report",
        "publish",
        "fixture",
        "fixture-e2e",
        "pilot",
        "acquisition",
    ):
        assert command in help_text


def test_publish_aggregate_help_uses_current_official_aggregate_contract(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["publish", "aggregate", "--help"])

    assert exc_info.value.code == 0
    help_text = capsys.readouterr().out
    for expected in (
        "--model-registry",
        "--baseline-training-examples",
        "--allow-no-baselines",
        "--deferred-ablation",
        "--paired-delta-sd",
    ):
        assert expected in help_text


def test_publish_site_renders_official_artifacts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    official_dir = write_official_report_fixture(tmp_path)
    output_dir = tmp_path / "site"

    assert (
        main(
            [
                "publish",
                "site",
                "--official-artifacts-dir",
                str(official_dir),
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    summary = json.loads(capsys.readouterr().out)
    assert Path(summary["index"]).is_file()
    assert Path(summary["artifact_index"]).is_file()


def test_case_dev_smoke_help_describes_operational_options(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["case-dev-smoke", "--help"])

    assert exc_info.value.code == 0
    help_text = capsys.readouterr().out
    for expected in (
        "Markdown report path",
        "recorded case.dev JSONL responses",
        "CASE_DEV_API_KEY",
        "planned report skeleton",
        "default optimized MTD decision-term set",
        "Inclusive filed_at lower bound",
        "Maximum docket-entry search hits",
        "Maximum discovered candidate cases",
    ):
        assert expected in help_text


def test_discover_cli_writes_candidates_and_search_terms(
    tmp_path: Path,
    capsys,
) -> None:
    docket_entries = tmp_path / "docket_entries.jsonl"
    docket_entries.write_text(
        "\n".join(
            json.dumps(record)
            for record in (
                {
                    "case_id": "case-1",
                    "docket_entry_id": "entry-12",
                    "entry_text": "Motion to dismiss complaint",
                },
                {
                    "case_id": "case-1",
                    "docket_entry_id": "entry-35",
                    "entry_text": (
                        "Opinion and order denying motion to dismiss at ECF No. 12"
                    ),
                },
            )
        )
        + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "candidates.jsonl"

    assert (
        main(
            [
                "discover",
                "--input",
                str(docket_entries),
                "--output",
                str(output),
                "--print-search-terms",
            ]
        )
        == 0
    )

    stdout = capsys.readouterr().out
    assert "dismissal" in stdout
    candidates = _read_jsonl(output)
    assert candidates[0]["case_id"] == "case-1"
    assert "motion to dismiss" in candidates[0]["trigger_terms"]


def test_fixture_e2e_cli_writes_benchmark_artifacts(tmp_path: Path) -> None:
    output_dir = tmp_path / "fixture"

    assert main(["fixture", "e2e", "--output-dir", str(output_dir)]) == 0

    manifest = json.loads(
        (output_dir / "artifact-manifest.json").read_text(encoding="utf-8")
    )
    for artifact in (
        "candidate-manifest.jsonl",
        "case-mix-diagnostics.json",
        "manifests/cycle_fixture_e2e.freeze.json",
        "artifact-index.json",
    ):
        assert artifact in manifest["artifacts"]
    assert not any("preregistration" in artifact for artifact in manifest["artifacts"])
    assert not (output_dir / "protocols").exists()
    assert "packets.jsonl" in manifest["artifacts"]
    assert "report/leaderboard.json" in manifest["artifacts"]

    candidate_manifest = _read_jsonl(output_dir / "candidate-manifest.jsonl")
    assert candidate_manifest[0]["eligibility_status"] == "eligible"
    assert candidate_manifest[0]["exclusion_status"] == "included"
    assert candidate_manifest[0]["case_mix_fields"]["press_publicity_tags"] == [
        "major_public_company_party"
    ]

    diagnostics = json.loads(
        (output_dir / "case-mix-diagnostics.json").read_text(encoding="utf-8")
    )
    assert diagnostics["cycle_id"] == "cycle_fixture_e2e"
    assert diagnostics["tables"]["press_publicity_tags"][0]["bucket"] == (
        "major_public_company_party"
    )

    freeze_bundle = json.loads(
        (output_dir / "manifests" / "cycle_fixture_e2e.freeze.json").read_text(
            encoding="utf-8"
        )
    )
    assert freeze_bundle["cycle_id"] == "cycle_fixture_e2e"
    assert {artifact["name"] for artifact in freeze_bundle["artifacts"]} == {
        "baselines",
        "cohort_policy",
        "execution_policy",
        "exclusion_ledger",
        "harness",
        "labels",
        "labeling_policy",
        "manifest",
        "model_registry",
        "prompt",
        "scorer",
        "units",
    }

    artifact_index = json.loads(
        (output_dir / "artifact-index.json").read_text(encoding="utf-8")
    )
    indexed_paths = {artifact["path"] for artifact in artifact_index["artifacts"]}
    assert "candidate-manifest.jsonl" in indexed_paths
    assert "report/leaderboard.json" in indexed_paths
    assert "artifact-index.json" not in indexed_paths
    assert all(artifact["sha256"] for artifact in artifact_index["artifacts"])

    run_records = _read_jsonl(output_dir / "runs.jsonl")
    assert {record["related_family_id"] for record in run_records} == {
        "fixture-related-family"
    }
    assert {record["mdl_family_id"] for record in run_records} == {"fixture-mdl-family"}
    score_payload = json.loads((output_dir / "scores.json").read_text(encoding="utf-8"))
    assert {
        unit_score["related_family_id"]
        for summary in score_payload["summaries"]
        for unit_score in summary["unit_scores"]
    } == {"fixture-related-family"}
    assert {
        unit_score["mdl_family_id"]
        for summary in score_payload["summaries"]
        for unit_score in summary["unit_scores"]
    } == {"fixture-mdl-family"}

    leaderboard = json.loads(
        (output_dir / "report" / "leaderboard.json").read_text(encoding="utf-8")
    )
    assert [row["model_id"] for row in leaderboard["rows"]] == [
        "model-a",
        "model-b",
    ]
    assert leaderboard["rows"][0]["micro_brier"] < leaderboard["rows"][1]["micro_brier"]
    assert leaderboard["pairwise_deltas"]
    assert leaderboard["calibration_tables"]
    assert leaderboard["calibration_plot_svg"].startswith("<svg")
    assert leaderboard["pareto_accuracy_cost"]
    assert {point["model_id"] for point in leaderboard["pareto_accuracy_cost"]} <= {
        "model-a",
        "model-b",
    }


def test_score_and_report_cli_reuse_fixture_artifacts(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "fixture"
    rerun_dir = tmp_path / "rerun"
    assert main(["fixture", "e2e", "--output-dir", str(fixture_dir)]) == 0

    scores = rerun_dir / "scores.json"
    unit_scores = rerun_dir / "unit_scores.jsonl"
    assert (
        main(
            [
                "score",
                "--runs",
                str(fixture_dir / "runs.jsonl"),
                "--labels",
                str(fixture_dir / "labels.jsonl"),
                "--output",
                str(scores),
                "--unit-scores-output",
                str(unit_scores),
            ]
        )
        == 0
    )

    report_dir = rerun_dir / "report"
    assert (
        main(
            [
                "report",
                "--scores",
                str(scores),
                "--accounting",
                str(fixture_dir / "accounting.jsonl"),
                "--output-dir",
                str(report_dir),
                "--title",
                "Rerun Leaderboard",
            ]
        )
        == 0
    )

    assert len(_read_jsonl(unit_scores)) == 2
    report_json = json.loads(
        (report_dir / "leaderboard.json").read_text(encoding="utf-8")
    )
    assert report_json["pairwise_deltas"]
    assert report_json["calibration_tables"]
    assert report_json["calibration_plot_svg"].startswith("<svg")
    assert report_json["pareto_accuracy_cost"]
    assert {point["model_id"] for point in report_json["pareto_accuracy_cost"]} <= {
        "model-a",
        "model-b",
    }
    assert "Rerun Leaderboard" in (report_dir / "leaderboard.md").read_text(
        encoding="utf-8"
    )
    assert (report_dir / "leaderboard.csv").is_file()


def test_pilot_readiness_cli_writes_blocked_live_report(tmp_path: Path) -> None:
    smoke_report = tmp_path / "phase0_case_dev_smoke.md"
    smoke_report.write_text(_blocked_smoke_report_text(), encoding="utf-8")
    fixture_dir = tmp_path / "fixture"
    assert main(["fixture", "e2e", "--output-dir", str(fixture_dir)]) == 0

    output_path = tmp_path / "phase0_post_feasibility_pilot.md"
    assert (
        main(
            [
                "pilot",
                "readiness",
                "--smoke-report",
                str(smoke_report),
                "--fixture-output-dir",
                str(fixture_dir),
                "--output",
                str(output_path),
                "--generated-at",
                "2026-05-14T12:00:00Z",
            ]
        )
        == 0
    )

    report = output_path.read_text(encoding="utf-8")
    assert "| Live clean packets produced | 0 |" in report
    assert "| Fixture E2E artifact path | passed |" in report
    assert "`docket_entry_listing_unavailable`" in report
    assert "not a key-permission problem" in report


def test_stage_commands_have_declared_dry_run_outputs(tmp_path: Path) -> None:
    input_file = tmp_path / "records.jsonl"
    input_file.write_text("", encoding="utf-8")
    scores = tmp_path / "scores.json"
    scores.write_text('{"summaries":[]}\n', encoding="utf-8")

    commands = (
        (
            "discover",
            ["--input", str(input_file), "--output", str(tmp_path / "discover.json")],
        ),
        (
            "retrieve",
            [
                "--candidates",
                str(input_file),
                "--output",
                str(tmp_path / "retrieve.json"),
            ],
        ),
        (
            "extract",
            [
                "--documents",
                str(input_file),
                "--output",
                str(tmp_path / "extract.json"),
            ],
        ),
        (
            "link",
            [
                "--retrievals",
                str(input_file),
                "--output",
                str(tmp_path / "link.json"),
            ],
        ),
        (
            "unitize",
            ["--input", str(input_file), "--output", str(tmp_path / "unitize.json")],
        ),
        (
            "label",
            ["--input", str(input_file), "--output", str(tmp_path / "label.json")],
        ),
        (
            "packet",
            [
                "build",
                "--input",
                str(input_file),
                "--output",
                str(tmp_path / "packet.json"),
            ],
        ),
        (
            "eval",
            [
                "run",
                "--packets",
                str(input_file),
                "--output",
                str(tmp_path / "run.json"),
                "--mock-output",
                "{}",
            ],
        ),
        (
            "score",
            [
                "--runs",
                str(input_file),
                "--labels",
                str(input_file),
                "--output",
                str(tmp_path / "score.json"),
            ],
        ),
        (
            "report",
            [
                "--scores",
                str(scores),
                "--output-dir",
                str(tmp_path / "report"),
            ],
        ),
    )

    for command, command_args in commands:
        assert main([command, *command_args, "--dry-run"]) == 0


def test_stage_commands_write_stable_dry_run_plans_and_logs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_file = tmp_path / "records.jsonl"
    input_file.write_text('{"case_id":"case-1"}\n{"case_id":"case-2"}\n')
    scores = tmp_path / "scores.json"
    scores.write_text('{"summaries":[{"model_id":"model-a"}]}\n', encoding="utf-8")

    report_dir = tmp_path / "report"
    fixture_dir = tmp_path / "fixture"
    run_output = tmp_path / "run.json"
    accounting_output = tmp_path / "accounting.jsonl"
    score_output = tmp_path / "score.json"
    unit_scores_output = tmp_path / "unit_scores.jsonl"

    cases = (
        (
            [
                "discover",
                "--input",
                str(input_file),
                "--output",
                str(tmp_path / "discover.json"),
            ],
            tmp_path / "discover.json",
            {
                "command": "discover",
                "dry_run": True,
                "input_path": str(input_file),
                "output_paths": [str(tmp_path / "discover.json")],
                "record_count": 2,
                "search_terms": list(mtd_discovery_search_terms()),
            },
            _dry_run_log("discover", tmp_path / "discover.json", record_count=2),
        ),
        (
            [
                "retrieve",
                "--candidates",
                str(input_file),
                "--output",
                str(tmp_path / "retrieve.json"),
            ],
            tmp_path / "retrieve.json",
            {
                "case_dev_fixture": "None",
                "command": "retrieve",
                "dry_run": True,
                "input_path": str(input_file),
                "live": False,
                "output_paths": [str(tmp_path / "retrieve.json")],
                "record_count": 2,
            },
            _dry_run_log("retrieve", tmp_path / "retrieve.json", record_count=2),
        ),
        (
            [
                "extract",
                "--documents",
                str(input_file),
                "--output",
                str(tmp_path / "extract.json"),
                "--text-output-dir",
                str(tmp_path / "texts"),
            ],
            tmp_path / "extract.json",
            {
                "command": "extract",
                "dry_run": True,
                "input_path": str(input_file),
                "output_paths": [str(tmp_path / "extract.json")],
                "record_count": 2,
                "text_output_dir": str(tmp_path / "texts"),
            },
            _dry_run_log("extract", tmp_path / "extract.json", record_count=2),
        ),
        (
            [
                "link",
                "--retrievals",
                str(input_file),
                "--output",
                str(tmp_path / "link.json"),
            ],
            tmp_path / "link.json",
            {
                "command": "link",
                "dry_run": True,
                "input_path": str(input_file),
                "output_paths": [str(tmp_path / "link.json")],
                "record_count": 2,
            },
            _dry_run_log("link", tmp_path / "link.json", record_count=2),
        ),
        (
            [
                "unitize",
                "--input",
                str(input_file),
                "--output",
                str(tmp_path / "unitize.json"),
            ],
            tmp_path / "unitize.json",
            {
                "command": "unitize",
                "dry_run": True,
                "input_path": str(input_file),
                "output_paths": [str(tmp_path / "unitize.json")],
                "record_count": 2,
            },
            _dry_run_log("unitize", tmp_path / "unitize.json", record_count=2),
        ),
        (
            [
                "label",
                "--input",
                str(input_file),
                "--output",
                str(tmp_path / "label.json"),
            ],
            tmp_path / "label.json",
            {
                "command": "label",
                "dry_run": True,
                "input_path": str(input_file),
                "output_paths": [str(tmp_path / "label.json")],
                "record_count": 2,
            },
            _dry_run_log("label", tmp_path / "label.json", record_count=2),
        ),
        (
            [
                "packet",
                "build",
                "--input",
                str(input_file),
                "--output",
                str(tmp_path / "packet.json"),
            ],
            tmp_path / "packet.json",
            {
                "ablation": "full_packet",
                "command": "packet-build",
                "dry_run": True,
                "input_path": str(input_file),
                "output_paths": [str(tmp_path / "packet.json")],
                "record_count": 2,
            },
            _dry_run_log("packet-build", tmp_path / "packet.json", record_count=2),
        ),
        (
            [
                "eval",
                "run",
                "--packets",
                str(input_file),
                "--output",
                str(run_output),
                "--accounting-output",
                str(accounting_output),
                "--mock-output",
                "{}",
            ],
            run_output,
            {
                "command": "model-run",
                "dry_run": True,
                "input_path": str(input_file),
                "output_paths": [str(run_output), str(accounting_output)],
                "record_count": 2,
                "solver_id": "offline:fixture",
            },
            _dry_run_log("model-run", run_output, record_count=2),
        ),
        (
            [
                "score",
                "--runs",
                str(input_file),
                "--labels",
                str(input_file),
                "--output",
                str(score_output),
                "--unit-scores-output",
                str(unit_scores_output),
            ],
            score_output,
            {
                "command": "score",
                "dry_run": True,
                "input_path": str(input_file),
                "label_count": 2,
                "output_paths": [str(score_output), str(unit_scores_output)],
                "record_count": 2,
            },
            _dry_run_log("score", score_output, record_count=2),
        ),
        (
            ["report", "--scores", str(scores), "--output-dir", str(report_dir)],
            report_dir / "report.plan.json",
            {
                "accounting_count": 0,
                "command": "report",
                "dry_run": True,
                "input_path": str(scores),
                "output_paths": _report_output_paths(report_dir),
                "record_count": 1,
            },
            _dry_run_log("report", report_dir / "report.plan.json"),
        ),
        (
            ["fixture", "e2e", "--output-dir", str(fixture_dir)],
            fixture_dir / "fixture-e2e.plan.json",
            {
                "command": "fixture-e2e",
                "dry_run": True,
                "output_paths": _fixture_output_paths(fixture_dir),
                "record_count": 1,
            },
            _dry_run_log("fixture-e2e", fixture_dir / "fixture-e2e.plan.json"),
        ),
    )

    for command_args, plan_path, expected_plan, expected_log in cases:
        assert main([*command_args, "--dry-run"]) == 0
        assert plan_path.read_text(encoding="utf-8") == _json_text(expected_plan)
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == _json_line(expected_log)


def test_hyphenated_cli_aliases_remain_supported(tmp_path: Path) -> None:
    input_file = tmp_path / "records.jsonl"
    input_file.write_text("", encoding="utf-8")

    assert (
        main(
            [
                "packet-build",
                "--input",
                str(input_file),
                "--output",
                str(tmp_path / "packet.json"),
                "--dry-run",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "model-run",
                "--packets",
                str(input_file),
                "--output",
                str(tmp_path / "run.json"),
                "--mock-output",
                "{}",
                "--dry-run",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "fixture-e2e",
                "--output-dir",
                str(tmp_path / "fixture"),
                "--dry-run",
            ]
        )
        == 0
    )


def test_console_entrypoint_preserves_freeze_help(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "argv", ["legalforecast", "freeze", "--help"])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _dry_run_log(
    stage: str,
    artifact_path: Path,
    *,
    record_count: int | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "artifact_path": str(artifact_path),
        "event": "dry_run",
        "stage": stage,
    }
    if record_count is not None:
        payload["record_count"] = record_count
    return payload


def _json_text(payload: dict[str, object]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _json_line(payload: dict[str, object]) -> str:
    return json.dumps(payload, sort_keys=True) + "\n"


def _blocked_smoke_report_text() -> str:
    return """# Phase 0 case.dev Smoke Report

## Run Configuration

- Generated at: 2026-05-14T19:05:37.526562Z

## Candidate Yield

- Total hit count: 144
- Unique candidate cases: 82
- Retrieved candidate cases: 0
- Clean MTD candidates: 0

## Missing Document Reasons

- docket_entry_listing_unavailable: 10

## Request And Cost Counts

- case.dev request count: 42
- Estimated case.dev cost: not configured

## Candidate Ledger

| Candidate ID | Case ID | Clean proxy | Missing reasons | Retrieval error |
| --- | --- | --- | --- | --- |
| case-dev-smoke-1 | 1 | no | docket_entry_listing_unavailable | unavailable |
| case-dev-smoke-2 | 2 | no | docket_entry_listing_unavailable | unavailable |
| case-dev-smoke-3 | 3 | no | docket_entry_listing_unavailable | unavailable |
| case-dev-smoke-4 | 4 | no | docket_entry_listing_unavailable | unavailable |
| case-dev-smoke-5 | 5 | no | docket_entry_listing_unavailable | unavailable |
| case-dev-smoke-6 | 6 | no | docket_entry_listing_unavailable | unavailable |
| case-dev-smoke-7 | 7 | no | docket_entry_listing_unavailable | unavailable |
| case-dev-smoke-8 | 8 | no | docket_entry_listing_unavailable | unavailable |
| case-dev-smoke-9 | 9 | no | docket_entry_listing_unavailable | unavailable |
| case-dev-smoke-10 | 10 | no | docket_entry_listing_unavailable | unavailable |
"""


def _report_output_paths(output_dir: Path) -> list[str]:
    return [
        str(output_dir / "leaderboard.json"),
        str(output_dir / "leaderboard.csv"),
        str(output_dir / "leaderboard.md"),
        str(output_dir / "leaderboard.html"),
    ]


def _fixture_output_paths(output_dir: Path) -> list[str]:
    return [
        str(output_dir / "docket_entries.jsonl"),
        str(output_dir / "candidates.jsonl"),
        str(output_dir / "retrievals.jsonl"),
        str(output_dir / "document-manifest.jsonl"),
        str(output_dir / "extracted_texts.jsonl"),
        str(output_dir / "linkage.jsonl"),
        str(output_dir / "eligibility.json"),
        str(output_dir / "case-mix-diagnostics.json"),
        str(output_dir / "exclusion-ledger.jsonl"),
        str(output_dir / "units.jsonl"),
        str(output_dir / "labels.jsonl"),
        str(output_dir / "candidate-manifest.jsonl"),
        str(output_dir / "packets.jsonl"),
        str(output_dir / "runs.jsonl"),
        str(output_dir / "accounting.jsonl"),
        str(output_dir / "scores.json"),
        str(output_dir / "prompt.md"),
        str(output_dir / "scorer.py"),
        str(output_dir / "harness.txt"),
        str(output_dir / "model-registry.json"),
        str(output_dir / "baselines.json"),
        str(output_dir / "labeling-policy.json"),
        str(output_dir / "cohort-policy.json"),
        str(output_dir / "execution-policy.json"),
        str(output_dir / "manifests" / "cycle_fixture_e2e.freeze.json"),
        str(output_dir / "report" / "leaderboard.json"),
        str(output_dir / "report" / "leaderboard.csv"),
        str(output_dir / "report" / "leaderboard.md"),
        str(output_dir / "report" / "leaderboard.html"),
        str(output_dir / "artifact-manifest.json"),
        str(output_dir / "artifact-index.json"),
    ]
