"""Scoreless terminal-release execution and portable host-side scoring."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.cli import main
from legalforecast.contracts import ARTIFACT_CANONICAL_JSON_V1
from legalforecast.multiharness.adapters import AdapterPreparation
from legalforecast.multiharness.release_adapters import NeutralApiFixtureAdapter
from legalforecast.multiharness.release_harness import (
    release_bytes_sha256,
    score_multiharness_release,
)
from legalforecast.multiharness.spec import (
    AdapterCapabilities,
    RunRequest,
    RunResult,
)
from legalforecast.multiharness.terminal_release import (
    execute_terminal_release_only,
    score_terminal_release,
)
from legalforecast.multiharness.terminal_release_cli import TerminalReleaseOptions
from legalforecast.multiharness.terminal_release_package import (
    load_terminal_release_run,
)
from legalforecast.release import (
    CaseDraft,
    DocumentDraft,
    ForecastDraft,
    LabelsDraft,
    PredictionUnitDraft,
    ScoringPolicy,
    UnitOutcome,
    issue_release,
)


class CaseBatchFixtureAdapter:
    """Return all predictions for a case in one neutral fixture invocation."""

    def __init__(
        self,
        *,
        failed_case_id: str | None = None,
        error_case_id: str | None = None,
    ) -> None:
        self.manifest = replace(
            NeutralApiFixtureAdapter(raw_output="{}").manifest,
            adapter_id="claude-code-container",
        )
        self.failed_case_id = failed_case_id
        self.error_case_id = error_case_id
        self.calls: list[str] = []

    def _delegate(self, request: RunRequest) -> NeutralApiFixtureAdapter:
        case_id = request.task.metadata["case_id"]
        required_unit_ids_raw = request.task.metadata["required_unit_ids"]
        assert isinstance(case_id, str)
        assert isinstance(required_unit_ids_raw, list)
        required_unit_ids = tuple(
            value
            for value in cast(list[object], required_unit_ids_raw)
            if isinstance(value, str)
        )
        self.calls.append(case_id)
        predictions: list[dict[str, Any]] = []
        if case_id != self.failed_case_id:
            predictions = [
                {
                    "unit_id": unit_id,
                    "probability_fully_dismissed": 0.25,
                }
                for unit_id in required_unit_ids
            ]
        raw_output = json.dumps(
            {"case_assessment": "fixture", "predictions": predictions},
            separators=(",", ":"),
        )
        return NeutralApiFixtureAdapter(raw_output=raw_output, manifest=self.manifest)

    def capabilities(self, workspace: Path) -> AdapterCapabilities:
        return self._delegate_for_capabilities().capabilities(workspace)

    def _delegate_for_capabilities(self) -> NeutralApiFixtureAdapter:
        return NeutralApiFixtureAdapter(raw_output="{}", manifest=self.manifest)

    def prepare(self, request: RunRequest, workspace: Path) -> AdapterPreparation:
        return self._delegate_for_capabilities().prepare(request, workspace)

    def run(self, request: RunRequest, workspace: Path) -> RunResult:
        return self._delegate(request).run(request, workspace)

    def run_with_solver_input(
        self,
        request: RunRequest,
        workspace: Path,
        solver_input_root: Path,
    ) -> RunResult:
        case_id = request.task.metadata["case_id"]
        if case_id == self.error_case_id:
            assert isinstance(case_id, str)
            self.calls.append(case_id)
            raise RuntimeError("fixture pre-projection failure")
        return self._delegate(request).run_with_solver_input(
            request, workspace, solver_input_root
        )


def _issue_unequal_case_release(tmp_path: Path) -> tuple[Path, Path]:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    case_specs = (
        ("case-001", ("unit-001", "unit-002")),
        ("case-002", ("unit-003",)),
    )
    cases: list[CaseDraft] = []
    units: list[PredictionUnitDraft] = []
    outcomes: list[UnitOutcome] = []
    for case_index, (case_id, unit_ids) in enumerate(case_specs, start=1):
        document = DocumentDraft(
            document_id=f"complaint-{case_id}",
            role="complaint",
            path=f"documents/{case_id}/complaint.txt",
        )
        document_path = artifact_root / document.path
        document_path.parent.mkdir(parents=True, exist_ok=True)
        document_path.write_text(f"visible source for {case_id}")
        prompt_path = artifact_root / f"prompts/{case_id}.txt"
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(f"shared blinded prompt for {case_id}")
        cases.append(CaseDraft(case_id=case_id, documents=(document,)))
        for unit_index, unit_id in enumerate(unit_ids, start=1):
            packet_path = artifact_root / f"packets/{unit_id}.json"
            packet_path.parent.mkdir(parents=True, exist_ok=True)
            packet_path.write_bytes(
                ARTIFACT_CANONICAL_JSON_V1.encode(
                    {
                        "case_id": case_id,
                        "claim_name": f"Claim {unit_id}",
                        "count": f"Count {case_index}.{unit_index}",
                        "decision_date": "2026-08-23",
                        "defendant_group": "defendants",
                        "model_visible_document_ids": [document.document_id],
                        "policy_digest": "1" * 64,
                        "unit_id": unit_id,
                    }
                )
            )
            units.append(
                PredictionUnitDraft(
                    unit_id=unit_id,
                    case_id=case_id,
                    claim_name=f"Claim {unit_id}",
                    defendant_group="defendants",
                    count=f"Count {case_index}.{unit_index}",
                    should_score=True,
                    model_visible_document_ids=(document.document_id,),
                    packet_path=packet_path.relative_to(artifact_root).as_posix(),
                    prompt_path=prompt_path.relative_to(artifact_root).as_posix(),
                )
            )
            outcomes.append(UnitOutcome(unit_id=unit_id, outcome=0))
    issued = issue_release(
        ForecastDraft(
            release_id="terminal-release-unequal-v1",
            policy_digest="1" * 64,
            code_version="fixture-code-v1",
            packet_builder_version="fixture-packet-v1",
            cases=tuple(cases),
            prediction_units=tuple(units),
        ),
        LabelsDraft(
            release_id="terminal-release-unequal-v1",
            scoring_policy=ScoringPolicy(policy_id="fixture-brier-v1"),
            unit_outcomes=tuple(outcomes),
        ),
        artifact_root=artifact_root,
    )
    release_root = tmp_path / "release"
    release_root.mkdir()
    (release_root / "forecast-release.json").write_bytes(
        issued.payloads["forecast-release.json"]
    )
    (release_root / "labels-release.json").write_bytes(
        issued.payloads["labels-release.json"]
    )
    return release_root, artifact_root


def _options(
    release_root: Path,
    artifact_root: Path,
    output_dir: Path,
) -> TerminalReleaseOptions:
    return TerminalReleaseOptions(
        forecast_release=release_root / "forecast-release.json",
        labels_release=None,
        artifact_root=artifact_root,
        output_dir=output_dir,
        model_key="fixture",
        image="sha256:" + "a" * 64,
        auth_profile="fixture-none",
        max_budget_usd=None,
        approval_reference=None,
        fixture_base_url="https://fixture.invalid:8080",
        fixture_egress_network=None,
        backend="docker",
        timeout_seconds=30,
        run_id="terminal-release-scoreless",
    )


def test_scoreless_execution_round_trip_scores_unequal_case_failure(
    tmp_path: Path,
) -> None:
    release_root, artifact_root = _issue_unequal_case_release(tmp_path)
    adapter = CaseBatchFixtureAdapter(failed_case_id="case-002")
    options = _options(release_root, artifact_root, tmp_path / "run")

    execute_terminal_release_only(options, adapter=adapter)
    report = score_terminal_release(
        run_dir=options.output_dir,
        forecast_release_path=options.forecast_release,
        labels_release_path=release_root / "labels-release.json",
        artifact_root=artifact_root,
        score=score_multiharness_release,
    )

    model = report["models"][0]
    assert adapter.calls == ["case-001", "case-002"]
    assert model["unit_count"] == 3
    assert model["completed_unit_count"] == 2
    assert model["failed_unit_count"] == 1
    assert model["micro_brier"] == (0.25**2 + 0.25**2 + 1.0) / 3
    assert model["equal_case_brier"] == (0.25**2 + 1.0) / 2
    assert report["headline_metrics_available"] is True


def test_release_execute_and_score_cli_separate_label_boundary(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    from legalforecast.multiharness import cli as multiharness_cli

    release_root, artifact_root = _issue_unequal_case_release(tmp_path)
    adapter = CaseBatchFixtureAdapter()

    def build_fixture_adapter(
        options: TerminalReleaseOptions, *, case_count: int
    ) -> CaseBatchFixtureAdapter:
        del options, case_count
        return adapter

    monkeypatch.setattr(
        multiharness_cli,
        "_build_terminal_release_adapter",
        build_fixture_adapter,
    )
    output = tmp_path / "cli-run"
    common = [
        "multiharness",
        "release-execute",
        "--forecast-release",
        str(release_root / "forecast-release.json"),
        "--artifact-root",
        str(artifact_root),
        "--output-dir",
        str(output),
        "--model-key",
        "fixture",
        "--image",
        "sha256:" + "a" * 64,
        "--fixture-base-url",
        "https://fixture.invalid:8080",
    ]
    assert main(common) == 0
    assert (output / "row-results.jsonl").is_file()
    assert not (output / "scores.json").exists()

    assert (
        main(
            [
                "multiharness",
                "release-score",
                "--run-dir",
                str(output),
                "--forecast-release",
                str(release_root / "forecast-release.json"),
                "--labels-release",
                str(release_root / "labels-release.json"),
                "--artifact-root",
                str(artifact_root),
            ]
        )
        == 0
    )
    assert (
        json.loads((output / "scores.json").read_text())["headline_metrics_available"]
        is True
    )


def test_saved_package_rejects_row_workspace_traversal(tmp_path: Path) -> None:
    release_root, artifact_root = _issue_unequal_case_release(tmp_path)
    options = _options(release_root, artifact_root, tmp_path / "run")
    execute_terminal_release_only(options, adapter=CaseBatchFixtureAdapter())
    row_results = options.output_dir / "row-results.jsonl"
    rewritten = json.loads(row_results.read_text().splitlines()[0])
    rewritten["row_id"] = "../outside"
    payload = (json.dumps(rewritten) + "\n").encode()
    row_results.write_bytes(payload)
    artifact_index_path = options.output_dir / "artifact-index.json"
    artifact_index = json.loads(artifact_index_path.read_text())
    row_results_record = next(
        item
        for item in artifact_index["artifacts"]
        if item["path"] == "row-results.jsonl"
    )
    row_results_record["sha256"] = release_bytes_sha256(payload)
    row_results_record["size_bytes"] = len(payload)
    artifact_index_path.write_text(json.dumps(artifact_index))

    with pytest.raises(ValueError, match="safe path component"):
        load_terminal_release_run(options.output_dir)


def test_saved_package_rejects_mutated_preprojection_failure_result(
    tmp_path: Path,
) -> None:
    release_root, artifact_root = _issue_unequal_case_release(tmp_path)
    options = _options(release_root, artifact_root, tmp_path / "run")
    execute_terminal_release_only(
        options,
        adapter=CaseBatchFixtureAdapter(error_case_id="case-002"),
    )
    result_path = next(
        path
        for path in (options.output_dir / "rows").glob("*/result.json")
        if "case-002"
        in json.loads((path.parent / "request.json").read_text())["task"]["metadata"][
            "case_id"
        ]
    )
    original_payload = result_path.read_text()
    result = json.loads(original_payload)
    original_error = result["public_summary"]["error_message"]
    result_path.write_text(
        original_payload.replace(original_error, "x" * len(original_error), 1)
    )

    with pytest.raises(ValueError, match="artifact digest does not match"):
        load_terminal_release_run(options.output_dir)
