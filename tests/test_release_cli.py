from __future__ import annotations

import json
from pathlib import Path

import pytest
from legalforecast.cli import main


def test_release_cli_issues_and_validates_synthetic_fixture(
    tmp_path: Path,
    capsys,
) -> None:
    output = tmp_path / "release"

    assert main(["release", "issue-synthetic", "--output-dir", str(output)]) == 0
    issue_status = json.loads(capsys.readouterr().out)
    assert issue_status["forecast_release"] == str(output / "forecast-release.json")
    assert issue_status["labels_release"] == str(output / "labels-release.json")

    assert (
        main(
            [
                "release",
                "validate",
                "--forecast",
                str(output / "forecast-release.json"),
                "--labels",
                str(output / "labels-release.json"),
                "--artifact-root",
                str(output),
            ]
        )
        == 0
    )
    validation = json.loads(capsys.readouterr().out)
    assert validation == {
        "case_count": 3,
        "forecast_release_digest": validation["forecast_release_digest"],
        "labels_release_digest": validation["labels_release_digest"],
        "release_id": "synthetic-three-case-v1",
        "unit_count": 3,
        "valid": True,
    }


def test_release_cli_help_exposes_generic_issuer(capsys) -> None:
    with pytest.raises(SystemExit, match="0"):
        main(["release", "issue", "--help"])
    help_text = capsys.readouterr().out
    assert "--forecast-draft" in help_text
    assert "--labels-draft" in help_text
    assert "--artifact-root" in help_text
    assert "--output-dir" in help_text


def test_generic_release_cli_issues_from_strict_drafts(tmp_path: Path, capsys) -> None:
    source = tmp_path / "source"
    assert main(["release", "issue-synthetic", "--output-dir", str(source)]) == 0
    capsys.readouterr()
    forecast = json.loads((source / "forecast-release.json").read_bytes())
    labels = json.loads((source / "labels-release.json").read_bytes())
    forecast_draft = {
        "release_id": forecast["release_id"],
        "policy_digest": forecast["policy_digest"],
        "code_version": forecast["code_version"],
        "packet_builder_version": forecast["packet_builder_version"],
        "cases": [
            {
                "case_id": case["case_id"],
                "documents": [
                    {
                        "document_id": document["document_id"],
                        "role": document["role"],
                        "path": document["path"],
                    }
                    for document in case["documents"]
                ],
            }
            for case in forecast["cases"]
        ],
        "prediction_units": [
            {
                "unit_id": unit["unit_id"],
                "case_id": unit["case_id"],
                "claim_name": unit["claim_name"],
                "defendant_group": unit["defendant_group"],
                "count": unit["count"],
                "should_score": unit["should_score"],
                "model_visible_document_ids": [
                    next(
                        case
                        for case in forecast["cases"]
                        if case["case_id"] == unit["case_id"]
                    )["documents"][index]["document_id"]
                    for index in unit["model_visible_document_indexes"]
                ],
                "packet_path": unit["packet_path"],
                "prompt_path": unit["prompt_path"],
            }
            for unit in forecast["prediction_units"]
        ],
    }
    labels_draft = {
        "release_id": labels["release_id"],
        "scoring_policy": labels["scoring_policy"],
        "unit_outcomes": labels["unit_outcomes"],
    }
    forecast_draft_path = tmp_path / "forecast-draft.json"
    labels_draft_path = tmp_path / "labels-draft.json"
    forecast_draft_path.write_text(json.dumps(forecast_draft), encoding="utf-8")
    labels_draft_path.write_text(json.dumps(labels_draft), encoding="utf-8")
    output = tmp_path / "issued"

    assert (
        main(
            [
                "release",
                "issue",
                "--forecast-draft",
                str(forecast_draft_path),
                "--labels-draft",
                str(labels_draft_path),
                "--artifact-root",
                str(source),
                "--output-dir",
                str(output),
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert (output / "forecast-release.json").read_bytes() == (
        source / "forecast-release.json"
    ).read_bytes()
    assert (output / "labels-release.json").read_bytes() == (
        source / "labels-release.json"
    ).read_bytes()
