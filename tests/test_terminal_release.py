"""Release-to-score integration with a credential-free solver fixture."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from legalforecast.cli import main
from legalforecast.multiharness import claude_code_container
from legalforecast.multiharness.release_adapters import NeutralApiFixtureAdapter
from legalforecast.multiharness.release_harness import score_multiharness_release
from legalforecast.multiharness.terminal_release import execute_terminal_release
from legalforecast.multiharness.terminal_release_cli import TerminalReleaseOptions
from legalforecast.release.synthetic import issue_synthetic_release


def test_terminal_release_scores_staged_case(tmp_path: Path) -> None:
    release_root = tmp_path / "release"
    issue_synthetic_release(release_root)
    adapter = NeutralApiFixtureAdapter(
        raw_output=json.dumps(
            {
                "case_assessment": "fixture",
                "predictions": [
                    {
                        "unit_id": "unit-001",
                        "probability_fully_dismissed": 0.25,
                    }
                ],
            }
        )
    )
    adapter = replace(
        adapter,
        manifest=replace(adapter.manifest, adapter_id="claude-code-container"),
    )
    output = tmp_path / "run"
    report = execute_terminal_release(
        TerminalReleaseOptions(
            forecast_release=release_root / "forecast-release.json",
            labels_release=release_root / "labels-release.json",
            artifact_root=release_root,
            output_dir=output,
            model_key="fixture",
            image="sha256:" + "a" * 64,
            auth_profile="fixture-none",
            max_budget_usd=None,
            approval_reference=None,
            fixture_base_url="https://fixture.invalid:8080",
            fixture_egress_network=None,
            backend="docker",
            timeout_seconds=30,
            run_id="terminal-release-fixture",
        ),
        adapter=adapter,
        score=score_multiharness_release,
    )

    assert report["models"][0]["completed_unit_count"] == 1
    assert (output / "scores.json").is_file()
    assert (output / "task-index.json").is_file()
    assert (output / "run-progress.json").is_file()


def test_terminal_release_refuses_unavailable_sandbox_before_scoring(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release_root = tmp_path / "release"
    issue_synthetic_release(release_root)
    monkeypatch.setattr(
        claude_code_container,
        "probe_native_claude_sandbox",
        lambda *_args, **_kwargs: False,
    )
    output = tmp_path / "run"
    status = main(
        [
            "multiharness",
            "release-run",
            "--forecast-release",
            str(release_root / "forecast-release.json"),
            "--labels-release",
            str(release_root / "labels-release.json"),
            "--artifact-root",
            str(release_root),
            "--output-dir",
            str(output),
            "--model-key",
            "anthropic:fixture",
            "--image",
            "sha256:" + "a" * 64,
            "--fixture-base-url",
            "https://fixture.invalid:8080",
        ]
    )
    assert status == 2
    assert not output.exists()
