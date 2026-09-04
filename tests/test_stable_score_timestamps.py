# pyright: reportPrivateUsage=false

from __future__ import annotations

import json
import os
import subprocess
from argparse import Namespace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from legalforecast import cli_support
from legalforecast.cli_commands import report as report_command
from legalforecast.cli_commands import score as score_command
from legalforecast.evals.model_registry import model_registry_sha256
from legalforecast.release import issue_synthetic_release, serialize_run_manifest
from tests.test_locked_run_manifest_consumer import (
    _manifest,
    _strict_receipts,
    _write_registry,
)

ROOT = Path(__file__).resolve().parents[1]
LOCKED_AT_ISO = "2026-08-30T12:01:00Z"
CLOCK_A = datetime(2026, 9, 4, 18, tzinfo=UTC)
CLOCK_B = datetime(2026, 9, 4, 19, tzinfo=UTC)


def test_same_run_score_bytes_reconcile_across_wall_clocks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retries of identical frozen scoring must reuse the published object.

    Green does not prove a live S3 bucket or a live Hugging Face dispatch.
    """

    inputs = _locked_inputs(tmp_path)
    first = _score_and_report(inputs, tmp_path / "first", monkeypatch, CLOCK_A)
    second = _score_and_report(inputs, tmp_path / "second", monkeypatch, CLOCK_B)

    assert first["scores"] == second["scores"]
    assert first["report"] == second["report"]
    score_payload = json.loads(first["scores"])
    report_payload = json.loads(first["report"])
    assert score_payload["generated_at"] == LOCKED_AT_ISO
    assert report_payload["generated_at"] == LOCKED_AT_ISO
    assert score_payload["generated_at"] != cli_support.iso_datetime(CLOCK_A)
    assert score_payload["generated_at"] != cli_support.iso_datetime(CLOCK_B)

    created = _reconcile(tmp_path, first["scores"], "scores.json")
    assert created.returncode == 0, created.stderr
    assert "created immutable S3 object" in created.stdout

    reused = _reconcile(tmp_path, second["scores"], "scores.json")
    assert reused.returncode == 0, reused.stderr
    assert "reused existing immutable S3 object" in reused.stdout

    report_created = _reconcile(tmp_path, first["report"], "report/leaderboard.json")
    assert report_created.returncode == 0, report_created.stderr
    report_reused = _reconcile(tmp_path, second["report"], "report/leaderboard.json")
    assert report_reused.returncode == 0, report_reused.stderr
    assert "reused existing immutable S3 object" in report_reused.stdout

    changed = json.loads(first["scores"])
    changed["summaries"][0]["micro_brier"] = 0.99
    mismatch = _reconcile(
        tmp_path,
        json.dumps(changed, indent=2, sort_keys=True, allow_nan=False) + "\n",
        "scores.json",
    )
    assert mismatch.returncode != 0
    assert "refusing S3 object mismatch" in mismatch.stderr


def _locked_inputs(tmp_path: Path) -> dict[str, Path | str]:
    release_dir = tmp_path / "release"
    issued = issue_synthetic_release(release_dir)
    registry_path = _write_registry(tmp_path)
    runs_path = tmp_path / "runs.jsonl"
    runs_path.write_text(
        "".join(
            json.dumps(record) + "\n"
            for record in _strict_receipts(issued, registry_path)
        ),
        encoding="utf-8",
    )
    manifest_path = tmp_path / "run-manifest.json"
    manifest_path.write_bytes(
        serialize_run_manifest(_manifest("case-001", "case-002", "case-003"))
    )
    return {
        "runs": runs_path,
        "labels_release": release_dir / "labels-release.json",
        "forecast_release": release_dir / "forecast-release.json",
        "artifact_root": release_dir,
        "manifest": manifest_path,
        "registry": registry_path,
        "registry_sha256": model_registry_sha256(registry_path.read_bytes()),
        "run_identity": "c" * 64,
    }


def _score_and_report(
    inputs: dict[str, Path | str],
    output_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    wall_clock: datetime,
) -> dict[str, str]:
    _freeze_wall_clock(monkeypatch, wall_clock)
    output_root.mkdir(parents=True, exist_ok=True)
    scores_path = output_root / "scores.json"
    report_dir = output_root / "report"
    assert (
        score_command.run(
            Namespace(
                runs=inputs["runs"],
                labels_release=inputs["labels_release"],
                forecast_release=inputs["forecast_release"],
                artifact_root=inputs["artifact_root"],
                manifest=inputs["manifest"],
                expected_run_identity_sha256=inputs["run_identity"],
                model_registry=inputs["registry"],
                expected_model_registry_sha256=inputs["registry_sha256"],
                ledger=None,
                output=scores_path,
                unit_scores_output=None,
                base_rate=None,
                include_ablation_in_model_id=False,
                dry_run=False,
            )
        )
        == 0
    )
    assert (
        report_command.run(
            Namespace(
                scores=scores_path,
                output_dir=report_dir,
                manifest=inputs["manifest"],
                forecast_release=inputs["forecast_release"],
                labels_release=inputs["labels_release"],
                artifact_root=inputs["artifact_root"],
                accounting=None,
                title="LegalForecast-MTD Leaderboard",
                bootstrap_replicates=1,
                bootstrap_seed=20260514,
                dry_run=False,
                model_registry=None,
                frozen_model_registry=None,
                expected_run_identity_sha256=inputs["run_identity"],
                expected_model_registry_sha256=inputs["registry_sha256"],
                ledger=None,
                contamination_boundary=None,
                cohort_id=None,
            )
        )
        == 0
    )
    return {
        "scores": scores_path.read_text(encoding="utf-8"),
        "report": (report_dir / "leaderboard.json").read_text(encoding="utf-8"),
    }


def _freeze_wall_clock(monkeypatch: pytest.MonkeyPatch, when: datetime) -> None:
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz: object | None = None) -> datetime:
            del tz
            return when

    monkeypatch.setattr(score_command, "datetime", FrozenDateTime, raising=False)
    monkeypatch.setattr(report_command, "datetime", FrozenDateTime, raising=False)
    monkeypatch.setattr(cli_support, "datetime", FrozenDateTime)


def _reconcile(
    tmp_path: Path,
    payload: str,
    key: str,
) -> subprocess.CompletedProcess[str]:
    fake_aws = tmp_path / "aws"
    if not fake_aws.exists():
        fake_aws.write_text(_FAKE_AWS, encoding="utf-8")
        fake_aws.chmod(0o755)
    source = tmp_path / "reconcile-source.json"
    source.write_text(payload, encoding="utf-8")
    environment = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "FAKE_AWS_STORE": str(tmp_path / "objects"),
    }
    return subprocess.run(
        [
            "bash",
            str(ROOT / ".github/scripts/reconcile-s3-object.sh"),
            "results-bucket",
            str(source),
            f"reports/cycle-1/multi-ablation/{key}",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )


_FAKE_AWS = """#!/usr/bin/env python3
import hashlib
import json
import os
import sys
from pathlib import Path

args = sys.argv[1:]
if args[:2] not in (["s3api", "head-object"], ["s3api", "put-object"]):
    raise SystemExit(f"unsupported fake aws call: {args}")
key = args[args.index("--key") + 1]
store = Path(os.environ["FAKE_AWS_STORE"])
store.mkdir(parents=True, exist_ok=True)
object_path = store / (hashlib.sha256(key.encode()).hexdigest() + ".json")
if args[1] == "head-object":
    if not object_path.is_file():
        print(
            "An error occurred (404) when calling HeadObject: Not Found",
            file=sys.stderr,
        )
        raise SystemExit(254)
    record = json.loads(object_path.read_text(encoding="utf-8"))
    print(json.dumps({"ContentLength": record["size"], "Metadata": record["metadata"]}))
else:
    if object_path.exists():
        print(
            "An error occurred (412) when calling PutObject: PreconditionFailed",
            file=sys.stderr,
        )
        raise SystemExit(412)
    body = Path(args[args.index("--body") + 1]).read_bytes()
    metadata = args[args.index("--metadata") + 1].split("=", 1)
    object_path.write_text(
        json.dumps({"size": len(body), "metadata": {metadata[0]: metadata[1]}}),
        encoding="utf-8",
    )
    print("created")
"""
