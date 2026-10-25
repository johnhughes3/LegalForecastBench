from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from scripts import legalreasonbench_model_runs as lrb


def _source(tmp_path: Path, *, include_scope: bool = False) -> tuple[Path, Path | None]:
    source = tmp_path / "source-index.json"
    source.write_text(
        json.dumps(
            {
                "dataset": lrb.DATASET,
                "revision": lrb.REVISION,
                "rows": [
                    {
                        "matter_id": "lrb-test-matter",
                        "assignment": 1,
                        "rubric": [
                            {
                                "criterion_id": "required_criterion",
                                "points": 5.0,
                                "polarity": "required",
                                "criterion": "Must include the required point.",
                            },
                            {
                                "criterion_id": "penalty_criterion",
                                "points": -3.0,
                                "polarity": "penalty",
                                "criterion": "Must not make the penalty statement.",
                            },
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    scope: Path | None = None
    if include_scope:
        scope = tmp_path / "in-scope.json"
        scope.write_text(
            json.dumps(
                {
                    "tasks": [
                        {
                            "matter_id": "lrb-test-matter",
                            "assignment": 1,
                            "in_scope": True,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
    return source, scope


def _panel_details(
    *, missing_judge: bool = False, judge_error: bool = False
) -> dict[str, Any]:
    models = [model for model, _label in lrb.JUDGES]

    def votes(values: list[int], *, negative: bool = False) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for model, value in zip(models, values, strict=True):
            vote: dict[str, Any] = {
                "judge": {"model": model, "reasoning_effort": "medium"},
                "name": "placeholder",
                "value": value,
                "raw": bool(1 - value if negative else value),
                "reasoning": f"Reasoning from {model}.",
            }
            if judge_error and not result:
                vote["error"] = "provider error"
            result.append(vote)
        if missing_judge:
            result.pop()
        return result

    criteria: list[dict[str, Any]] = [
        {
            "name": "required_criterion",
            "value": 1.0,
            "raw": True,
            "weight": 5.0,
            "signed_score": 5.0,
            "polarity": "positive",
            "contribution": 5.0,
            "description": "Must include the required point.",
            "votes": votes([1, 0, 1]),
        },
        {
            "name": "penalty_criterion",
            "value": 1.0,
            "raw": False,
            "weight": -3.0,
            "signed_score": -3.0,
            "polarity": "negative",
            "contribution": -3.0,
            "description": "Must not make the penalty statement.",
            "votes": votes([1, 1, 0], negative=True),
        },
    ]
    for criterion in criteria:
        for vote in criterion["votes"]:
            vote["name"] = criterion["name"]
    return {
        "correctness": {
            "score": 0.4,
            "kind": "signed_score",
            "criteria": criteria,
            "aggregation": {
                "method": "signed_score_ratio_clamped",
                "earned": 2.0,
                "positive_total": 5.0,
                "unclamped": 0.4,
                "clamped": 0.4,
            },
            "raw_rewardkit": {
                "criteria": [
                    {"name": "required_criterion", "negate": False},
                    {"name": "penalty_criterion", "negate": True},
                ]
            },
        }
    }


def _trial(
    root: Path,
    *,
    condition: str = "gpt6luna-xhigh",
    with_grades: bool = True,
    details: dict[str, Any] | None = None,
) -> tuple[bytes, bytes, bytes]:
    trial_dir = root / "job" / "trial-1"
    step = trial_dir / "steps" / "assignment-1"
    verifier = step / "verifier"
    verifier.mkdir(parents=True)
    model, variant = {
        "gpt6luna-xhigh": ("openai/gpt-6-luna", "xhigh"),
        "opus55-low": ("anthropic/claude-opus-5-5", "low"),
    }[condition]
    config = {"agent": {"model_name": model, "kwargs": {"variant": variant}}}
    (trial_dir / "config.json").write_text(json.dumps(config), encoding="utf-8")
    result = {
        "task_name": "micro1/lrb-test-matter",
        "agent_info": {
            "model_info": {
                "provider": model.split("/", 1)[0],
                "name": model.split("/", 1)[1],
            }
        },
    }
    (trial_dir / "result.json").write_text(json.dumps(result), encoding="utf-8")
    answer = b"# Exact answer\n\nTrailing spaces stay.  \n"
    (verifier / "answer.md").write_bytes(answer)
    reward = b'{"correctness": 0.4}\n'
    detail_bytes = json.dumps(details or _panel_details(), indent=2).encode() + b"\n"
    if with_grades:
        (verifier / "reward.json").write_bytes(reward)
        (verifier / "reward-details.json").write_bytes(detail_bytes)
    return answer, reward, detail_bytes


def _assignment(tmp_path: Path) -> lrb.Assignment:
    source, scope = _source(tmp_path, include_scope=True)
    return next(iter(lrb.load_assignments(source, scope).values()))


def test_import_preserves_answer_and_raw_scores_and_labels_penalties(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, _scope = _source(tmp_path)
    runs_root = tmp_path / "runs"
    answer, reward, details = _trial(runs_root / "gpt6luna-xhigh")
    output = tmp_path / "published"

    summary = lrb.import_runs(
        runs_root=runs_root,
        source_index=source,
        scope_index=None,
        output=output,
    )

    assert summary == {
        "assignments": 1,
        "answers": 1,
        "complete": 1,
        "partial": 0,
        "missing": 1,
    }
    published = output / "lrb-test-matter-assignment-1" / "gpt6luna-xhigh"
    assert (published / "response.md").read_bytes() == answer
    assert (published / "reward.json").read_bytes() == reward
    assert (published / "reward-details.json").read_bytes() == details
    assignment = _assignment(tmp_path)

    def assignments(*_args: object, **_kwargs: object) -> dict[str, lrb.Assignment]:
        return {assignment.assignment_id: assignment}

    monkeypatch.setattr(lrb, "load_assignments", assignments)
    read = lrb.read_run("lrb-test-matter-assignment-1", "gpt6luna-xhigh", output)
    assert read["response"] == answer
    assert "**PENALTY TRIGGERED**" in lrb.run_grades(
        "lrb-test-matter-assignment-1", "penalty_criterion", "", output
    )
    block = lrb.run_block(
        "lrb-test-matter-assignment-1", "penalty_criterion", "", output
    )
    assert "<details>" in block
    assert "PENALTY TRIGGERED" in block
    assert "Reasoning from openai/gpt-5.6-terra." in block
    assert (
        "[answer](model-runs/lrb-test-matter-assignment-1/"
        "gpt6luna-xhigh/response.md)" in block
    )
    assert lrb.run_block("missing-assignment", "criterion", "", output) == ""
    page = (published / "README.md").read_text(encoding="utf-8")
    assert "openai/gpt-5.6-terra" in page
    assert "Reasoning from anthropic/claude-sonnet-5." in page
    assert "| -3 | penalty | **PENALTY TRIGGERED**" in page
    assert "| -3 |" in page


def test_validate_panel_rejects_missing_judge_and_judge_error(tmp_path: Path) -> None:
    assignment = _assignment(tmp_path)
    missing = _panel_details(missing_judge=True)
    errored = _panel_details(judge_error=True)

    with pytest.raises(lrb.IncompletePanel, match="three judge votes"):
        lrb.validate_panel(missing, assignment)
    with pytest.raises(lrb.IncompletePanel, match="returned an error"):
        lrb.validate_panel(errored, assignment)


def test_validate_panel_rejects_criterion_weight_mismatch(tmp_path: Path) -> None:
    assignment = _assignment(tmp_path)
    details = _panel_details()
    details["correctness"]["criteria"][0]["weight"] = 99

    with pytest.raises(lrb.CriterionMismatch, match="weight mismatch"):
        lrb.validate_panel(details, assignment)


def test_validate_panel_rejects_aggregation_or_majority_mismatch(
    tmp_path: Path,
) -> None:
    assignment = _assignment(tmp_path)
    polarity_does_not_supply_negate = _panel_details()
    polarity_does_not_supply_negate["correctness"]["raw_rewardkit"]["criteria"][1][
        "negate"
    ] = False
    penalty = polarity_does_not_supply_negate["correctness"]["criteria"][1]
    penalty["raw"] = True
    for vote in penalty["votes"]:
        vote["raw"] = bool(vote["value"])
    lrb.validate_panel(polarity_does_not_supply_negate, assignment)

    details = _panel_details()
    details["correctness"]["criteria"][0]["value"] = 0
    details["correctness"]["criteria"][0]["raw"] = False
    details["correctness"]["criteria"][0]["contribution"] = 0

    with pytest.raises(lrb.CriterionMismatch, match="majority value mismatch"):
        lrb.validate_panel(details, assignment)

    details = _panel_details()
    details["correctness"]["aggregation"]["clamped"] = 0.5
    with pytest.raises(lrb.CriterionMismatch, match="aggregation score mismatch"):
        lrb.validate_panel(details, assignment)

    with pytest.raises(lrb.CriterionMismatch, match="scores differ"):
        lrb.validate_panel(_panel_details(), assignment, {"correctness": 0.5})


def test_import_refuses_conflicting_existing_files_without_deleting_them(
    tmp_path: Path,
) -> None:
    source, _scope = _source(tmp_path)
    runs_root = tmp_path / "runs"
    _trial(runs_root / "gpt6luna-xhigh")
    output = tmp_path / "published"
    old_response = (
        output / "lrb-test-matter-assignment-1" / "gpt6luna-xhigh" / "response.md"
    )
    old_response.parent.mkdir(parents=True)
    old_response.write_bytes(b"old published answer")
    keep = output / "keep.txt"
    keep.write_text("keep", encoding="utf-8")

    with pytest.raises(lrb.NativeRunError, match="refusing to overwrite"):
        lrb.import_runs(
            runs_root=runs_root,
            source_index=source,
            scope_index=None,
            output=output,
        )

    assert old_response.read_bytes() == b"old published answer"
    assert keep.read_text(encoding="utf-8") == "keep"


def test_import_refuses_wrong_model_identity(tmp_path: Path) -> None:
    source, _scope = _source(tmp_path)
    runs_root = tmp_path / "runs"
    _trial(runs_root / "gpt6luna-xhigh")
    config = runs_root / "gpt6luna-xhigh" / "job" / "trial-1" / "config.json"
    config.write_text(
        json.dumps(
            {
                "agent": {
                    "model_name": "openai/wrong-model",
                    "kwargs": {"variant": "xhigh"},
                }
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "published"

    with pytest.raises(lrb.NativeRunError, match="model identity"):
        lrb.import_runs(
            runs_root=runs_root,
            source_index=source,
            scope_index=None,
            output=output,
        )
    assert not output.exists()


def test_partial_answer_is_published_without_inventing_grades(tmp_path: Path) -> None:
    source, _scope = _source(tmp_path)
    runs_root = tmp_path / "runs"
    answer, _reward, _details = _trial(
        runs_root / "opus55-low", condition="opus55-low", with_grades=False
    )
    output = tmp_path / "published"

    summary = lrb.import_runs(
        runs_root=runs_root,
        source_index=source,
        scope_index=None,
        output=output,
    )

    published = output / "lrb-test-matter-assignment-1" / "opus55-low"
    assert summary["answers"] == 1
    assert summary["complete"] == 0
    assert summary["partial"] == 1
    assert (published / "response.md").read_bytes() == answer
    assert not (published / "reward.json").exists()
    assert "no criterion failure is assigned" in (published / "README.md").read_text()
    block = lrb.run_block(
        "lrb-test-matter-assignment-1", "required_criterion", "", output
    )
    assert "Grade panel unavailable or incomplete" in block
    assert "**Status:**" not in block

    verifier = (
        runs_root
        / "opus55-low"
        / "job"
        / "trial-1"
        / "steps"
        / "assignment-1"
        / "verifier"
    )
    verifier.joinpath("reward.json").write_bytes(b'{"correctness": 0.4}\n')
    verifier.joinpath("reward-details.json").write_bytes(
        json.dumps(_panel_details(), indent=2).encode() + b"\n"
    )
    summary = lrb.import_runs(
        runs_root=runs_root,
        source_index=source,
        scope_index=None,
        output=output,
    )
    assert summary["complete"] == 1
    assert (published / "reward.json").exists()
    assert "complete three-judge panel" in (published / "README.md").read_text()
