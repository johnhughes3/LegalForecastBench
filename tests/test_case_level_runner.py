from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from pathlib import Path
from typing import cast
from urllib.request import Request

import pytest
from legalforecast.contracts import ARTIFACT_CANONICAL_JSON_V1
from legalforecast.release import (
    CaseDraft,
    DocumentDraft,
    ForecastDraft,
    LabelsDraft,
    PredictionUnitDraft,
    ScoringPolicy,
    UnitOutcome,
    case_has_scored_units,
    enumerate_forecast_worker_inputs,
    issue_release,
    load_forecast_execution,
)
from legalforecast.runner import RunConfig, RunValidationError, execute_release_run
from legalforecast.runner.fixture import FIXTURE_MODEL_KEY, issue_runner_fixture


class CountingCaseTransport:
    def __init__(self) -> None:
        self.requests: list[Request] = []

    def __call__(self, request: Request, timeout_seconds: float) -> dict[str, object]:
        del timeout_seconds
        self.requests.append(request)
        assert request.data is not None
        body = cast(dict[str, object], json.loads(cast(bytes, request.data)))
        prompt = cast(str, body["input"])
        assert "unit-a" in prompt and "unit-b" in prompt
        return {
            "model": "legalforecast-fixture-2026-08-23",
            "output_text": json.dumps(
                {
                    "case_assessment": "case-level fixture",
                    "predictions": [
                        {
                            "unit_id": "unit-a",
                            "probability_fully_dismissed": 0.2,
                        },
                        {
                            "unit_id": "unit-b",
                            "probability_fully_dismissed": 0.8,
                        },
                    ],
                },
                sort_keys=True,
            ),
            "service_tier": "flex",
            "status": "completed",
            "usage": {"input_tokens": 20, "output_tokens": 10},
        }


@pytest.mark.parametrize(
    ("scoreability", "expected"),
    [
        ((False, None), False),
        ((False, None, True), True),
        ((), False),
    ],
)
def test_case_has_scored_units_requires_explicit_true(
    scoreability: tuple[bool | None, ...], expected: bool
) -> None:
    assert case_has_scored_units(iter(scoreability)) is expected


def test_case_level_runner_calls_provider_once_and_resumes_by_full_unit_set(
    tmp_path: Path,
) -> None:
    config = _case_config(tmp_path, scoreability=(True, False))
    transport = CountingCaseTransport()

    first = execute_release_run(
        config,
        transport=transport,
        environ={"OPENAI_API_KEY": "provider-free-case-test"},
    )

    assert first.completed_cells == 1
    assert first.executed_cells == 1
    assert first.resumed_cells == 0
    assert len(transport.requests) == 1
    receipts = tuple(config.receipts_dir.glob("*.json"))
    assert len(receipts) == 1
    receipt = json.loads(receipts[0].read_bytes())
    assert receipt["unit_id"] is None
    assert receipt["required_unit_ids"] == ["unit-a", "unit-b"]
    assert receipt["parser_output"]["required_unit_ids"] == ["unit-a", "unit-b"]

    with sqlite3.connect(config.ledger_path) as connection:
        row = connection.execute(
            "SELECT case_id, unit_id, required_unit_ids_json FROM public_runner_cells"
        ).fetchone()
        assert row is not None
        assert row[0] == "case-001"
        assert str(row[1]).startswith("case-call:case-001:")
        assert json.loads(row[2]) == ["unit-a", "unit-b"]
        assert connection.execute(
            "SELECT COUNT(*) FROM provider_attempts"
        ).fetchone() == (1,)

    resumed = execute_release_run(
        config,
        transport=CountingCaseTransport(),
        environ={"OPENAI_API_KEY": "provider-free-case-test"},
    )
    assert resumed.completed_cells == 1
    assert resumed.executed_cells == 0
    assert resumed.resumed_cells == 1


def test_runner_rejects_all_unscored_case_before_provider_spend(
    tmp_path: Path,
) -> None:
    config = _all_unscored_case_config(tmp_path)
    transport = CountingCaseTransport()

    with pytest.raises(
        RunValidationError, match=r"case_has_no_scored_units.*case-001"
    ) as exc:
        execute_release_run(
            config,
            transport=transport,
            environ={"OPENAI_API_KEY": "provider-free-case-test"},
        )

    error = exc.value
    assert getattr(error, "code", None) == "case_has_no_scored_units"
    assert getattr(error, "case_ids", None) == ("case-001",)
    assert transport.requests == []
    assert not config.ledger_path.exists()


def test_case_level_runner_rejects_partial_unit_selection(tmp_path: Path) -> None:
    config = _case_config(tmp_path)

    with pytest.raises(RunValidationError, match="part of"):
        execute_release_run(
            replace(config, unit_id="unit-a"),
            transport=CountingCaseTransport(),
            environ={"OPENAI_API_KEY": "provider-free-case-test"},
        )


def test_worker_inputs_emit_one_shared_case_prompt(tmp_path: Path) -> None:
    config = _case_config(tmp_path)
    release = load_forecast_execution(
        config.forecast_path,
        artifact_root=config.artifact_root,
    ).release

    prompts = tuple(
        item
        for item in enumerate_forecast_worker_inputs(release)
        if item.kind == "prompt"
    )

    assert len(prompts) == 1
    assert prompts[0].relative_path == "prompts/case-001.txt"
    assert prompts[0].case_id == "case-001"
    assert prompts[0].unit_id is None


def _case_config(
    tmp_path: Path, *, scoreability: tuple[bool, bool] = (True, True)
) -> RunConfig:
    fixture = tmp_path / "fixture"
    issue_runner_fixture(fixture)
    release_root = tmp_path / "case-release"
    release_root.mkdir()
    prompt = b"Forecast unit-a and unit-b from this shared case envelope.\n"
    documents = (
        DocumentDraft(
            document_id="case-001-motion",
            role="motion_to_dismiss_memorandum",
            path="documents/case-001/motion.txt",
        ),
    )
    payloads = {
        "documents/case-001/motion.txt": b"motion",
        "prompts/case-001.txt": prompt,
    }
    for unit_id in ("unit-a", "unit-b"):
        payloads[f"packets/{unit_id}.json"] = ARTIFACT_CANONICAL_JSON_V1.encode(
            {
                "case_id": "case-001",
                "decision_date": "2026-08-23",
                "unit_id": unit_id,
            }
        )
    for relative, payload in payloads.items():
        path = release_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    issued = issue_release(
        ForecastDraft(
            release_id="case-level-runner",
            policy_digest="1" * 64,
            code_version="case-level",
            packet_builder_version="case-level",
            cases=(CaseDraft(case_id="case-001", documents=documents),),
            prediction_units=tuple(
                PredictionUnitDraft(
                    unit_id=unit_id,
                    case_id="case-001",
                    claim_name=unit_id,
                    defendant_group="defendants",
                    count="Count I",
                    should_score=scoreability[index],
                    model_visible_document_ids=("case-001-motion",),
                    packet_path=f"packets/{unit_id}.json",
                    prompt_path="prompts/case-001.txt",
                )
                for index, unit_id in enumerate(("unit-a", "unit-b"))
            ),
        ),
        LabelsDraft(
            release_id="case-level-runner",
            scoring_policy=ScoringPolicy(policy_id="case-level"),
            unit_outcomes=tuple(
                UnitOutcome(unit_id=unit_id, outcome=index)
                for index, unit_id in enumerate(("unit-a", "unit-b"))
                if scoreability[index]
            ),
        ),
        artifact_root=release_root,
    )
    (release_root / "forecast-release.json").write_bytes(
        ARTIFACT_CANONICAL_JSON_V1.encode(issued.forecast.model_dump(mode="json"))
    )
    return RunConfig(
        forecast_path=release_root / "forecast-release.json",
        artifact_root=release_root,
        model_registry_path=fixture / "model-registry.json",
        model_key=FIXTURE_MODEL_KEY,
        ledger_path=tmp_path / "runner.sqlite3",
        receipts_dir=tmp_path / "receipts",
        ceiling_microusd=30_000,
        approval_reference="case-level-test",
    )


def _all_unscored_case_config(tmp_path: Path) -> RunConfig:
    fixture = tmp_path / "fixture"
    issue_runner_fixture(fixture)
    release_root = tmp_path / "case-release"
    release_root.mkdir()
    documents = tuple(
        DocumentDraft(
            document_id=f"{case_id}-motion",
            role="motion_to_dismiss_memorandum",
            path=f"documents/{case_id}/motion.txt",
        )
        for case_id in ("case-001", "case-002")
    )
    payloads: dict[str, bytes] = {}
    for document in documents:
        payloads[document.path] = b"motion"
    payloads.update(
        {
            "prompts/case-001.txt": b"Forecast the all-unscored case.\n",
            "prompts/case-002.txt": b"Forecast the scoreable case.\n",
            "packets/unit-a.json": ARTIFACT_CANONICAL_JSON_V1.encode(
                {"case_id": "case-001", "decision_date": "2026-08-23"}
            ),
            "packets/unit-b.json": ARTIFACT_CANONICAL_JSON_V1.encode(
                {"case_id": "case-002", "decision_date": "2026-08-23"}
            ),
        }
    )
    for relative, payload in payloads.items():
        path = release_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    issued = issue_release(
        ForecastDraft(
            release_id="all-unscored-case-runner",
            policy_digest="1" * 64,
            code_version="case-level",
            packet_builder_version="case-level",
            cases=tuple(
                CaseDraft(case_id=case_id, documents=(documents[index],))
                for index, case_id in enumerate(("case-001", "case-002"))
            ),
            prediction_units=(
                PredictionUnitDraft(
                    unit_id="unit-a",
                    case_id="case-001",
                    claim_name="unscored",
                    defendant_group="defendants",
                    count="Count I",
                    should_score=False,
                    model_visible_document_ids=("case-001-motion",),
                    packet_path="packets/unit-a.json",
                    prompt_path="prompts/case-001.txt",
                ),
                PredictionUnitDraft(
                    unit_id="unit-b",
                    case_id="case-002",
                    claim_name="scored",
                    defendant_group="defendants",
                    count="Count I",
                    should_score=True,
                    model_visible_document_ids=("case-002-motion",),
                    packet_path="packets/unit-b.json",
                    prompt_path="prompts/case-002.txt",
                ),
            ),
        ),
        LabelsDraft(
            release_id="all-unscored-case-runner",
            scoring_policy=ScoringPolicy(policy_id="case-level"),
            unit_outcomes=(UnitOutcome(unit_id="unit-b", outcome=1),),
        ),
        artifact_root=release_root,
    )
    (release_root / "forecast-release.json").write_bytes(
        ARTIFACT_CANONICAL_JSON_V1.encode(issued.forecast.model_dump(mode="json"))
    )
    return RunConfig(
        forecast_path=release_root / "forecast-release.json",
        artifact_root=release_root,
        model_registry_path=fixture / "model-registry.json",
        model_key=FIXTURE_MODEL_KEY,
        ledger_path=tmp_path / "runner.sqlite3",
        receipts_dir=tmp_path / "receipts",
        ceiling_microusd=30_000,
        approval_reference="case-level-test",
    )
