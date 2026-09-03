from __future__ import annotations

import json
from pathlib import Path

from legalforecast.cli import main


def test_runner_fixture_is_a_valid_public_release(tmp_path: Path) -> None:
    output_dir = tmp_path / "fixture-run"

    assert (
        main(
            [
                "run",
                "issue-fixture",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    forecast = output_dir / "release" / "forecast-release.json"
    labels = output_dir / "release" / "labels-release.json"
    assert forecast.is_file()
    assert labels.is_file()
    assert (output_dir / "model-registry.json").is_file()

    forecast_record = json.loads(forecast.read_text(encoding="utf-8"))
    labels_record = json.loads(labels.read_text(encoding="utf-8"))
    assert forecast_record["schema_version"] == "legalforecast.forecast-release.v1"
    assert labels_record["schema_version"] == "legalforecast.labels-release.v1"

    assert (
        main(
            [
                "release",
                "validate",
                "--forecast",
                str(forecast),
                "--labels",
                str(labels),
                "--artifact-root",
                str(output_dir / "release"),
            ]
        )
        == 0
    )
