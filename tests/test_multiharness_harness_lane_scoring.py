"""Both legs of the harness lane, driven all the way to a scored number.

``test_multiharness_harness_lane_run`` proves the lane *runs*; this module
proves it *scores*.  The legs score through different doors on purpose: LFB
rows reach ``lfb/runs.jsonl`` and ``legalforecast score`` over ``lfb_brier``,
which needs an authenticated ``forecast-release.v1`` corpus; Harvey LAB rows
reach ``lab/scores.jsonl`` through LAB's own isolated evaluator and never
touch ``lfb_brier`` at all.

No provider and no real container: ``fake_container`` writes the envelope the
manifest says to read, and the LAB judge is the committed fixture one.  What
is proven is the wiring and the bindings, not any model's behavior.
"""

from __future__ import annotations

import io
import json
import os
import stat
import sys
import zipfile
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from legalforecast.multiharness.harness_lane.lab_scoring import (
    LabScoringError,
    score_harness_lane_lab_run,
)
from legalforecast.multiharness.harvey_lab_evaluator import EVALUATOR_COMMAND_NAME
from legalforecast.multiharness.harvey_lab_projection import ISSUE_196_LAB_TASK_ID
from legalforecast.multiharness.local_cli_manifest import capability_digest_for
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService
from legalforecast.multiharness.task_loaders import ReleaseLfbTaskLoader
from legalforecast.multiharness.validation import validate_public_record
from legalforecast.release.synthetic import issue_synthetic_release
from tests.test_multiharness_harness_lane_run import (
    CONTAINER_MANIFEST,
    LAB_MANIFEST,
    LFB_ADAPTER,
    PROVIDER_HOST,
    _label_record,  # pyright: ignore[reportPrivateUsage]
    _lane_manifest_record,  # pyright: ignore[reportPrivateUsage]
    _run_multiharness,  # pyright: ignore[reportPrivateUsage]
    _scored_spec,  # pyright: ignore[reportPrivateUsage]
    run_legalforecast,
)
from tests.test_multiharness_harness_lane_run import (
    fake_container as fake_container,
)
from tests.test_multiharness_scoped_runs import projected_lab_layout

# Repository-relative, like the manifest constants this module imports: the
# suite's rootdir is the repository root, and a ``__file__``-relative spelling
# would put this module in the path-identity inventory for no benefit.
FAKE_EVALUATOR = Path(
    "tests/fixtures/claude_code/fake_harvey_lab_authorized_evaluator.py"
)
# Deterministic fixture issuer key. The signer and the issuer public key are
# parameters of the LAB composition precisely so a fixture judge can never be
# mistaken for the production one; this is the fixture.
LAB_ISSUER_KEY = Ed25519PrivateKey.from_private_bytes(b"S" * 32)


def test_lfb_release_task_source_scores_end_to_end(
    tmp_path: Path, fake_container: dict[str, Any]
) -> None:
    """``--task-source lfb --forecast-release`` reaches ``legalforecast score``.

    This is the LFB half of the lane's scoring chain, driven the way an
    operator drives it: no pre-built ``--task-index``, no hand-written solver
    input store.  The run resolves the release in place, writes the private
    prompts itself, hands the container the exact prompt bytes, and lands a
    row that ``legalforecast score`` turns into an actual number.
    """

    release_root = tmp_path / "release"
    issue_synthetic_release(release_root)
    forecast_release = release_root / "forecast-release.json"
    # Discover the scored unit without writing a store: the run owns that root.
    probe = ReleaseLfbTaskLoader().load_forecast_release(
        forecast_release, artifact_root=release_root
    )
    scored = next(task for task in probe.tasks if task.metadata["should_score"])
    unit_id = str(scored.metadata["unit_id"])
    prompt = (release_root / "prompts" / f"{unit_id}.txt").read_text(encoding="utf-8")
    fake_container["answer"] = json.dumps(
        {
            "case_assessment": "Release-sourced container-lane fixture answer.",
            "predictions": [{"unit_id": unit_id, "probability_fully_dismissed": 0.25}],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    output_dir = tmp_path / "run"

    assert (
        _run_multiharness(
            [
                "multiharness",
                "run",
                "--task-source",
                "lfb",
                "--forecast-release",
                str(forecast_release),
                "--artifact-root",
                str(release_root),
                "--solver-input-root",
                str(tmp_path / "solver-inputs"),
                "--adapter",
                LFB_ADAPTER,
                "--local-cli-manifest",
                str(CONTAINER_MANIFEST / "local-cli-adapter-manifest.json"),
                "--auth-profile",
                "fixture-none",
                "--allow-host",
                PROVIDER_HOST,
                "--model-key",
                "claude:fixture",
                "--task-id",
                scored.task_id,
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    # The exact private prompt reached the container and nothing published it.
    assert prompt in _scored_spec(fake_container).harness_argv
    for name in ("row-results.jsonl", "canonical-runs.jsonl"):
        assert prompt not in (output_dir / name).read_text(encoding="utf-8")

    lfb_runs = output_dir / "lfb" / "runs.jsonl"
    records = [
        json.loads(line) for line in lfb_runs.read_text(encoding="utf-8").splitlines()
    ]
    assert len(records) == 1
    # The lane keeps its identity in the scored row: this is a harness-vs-API
    # measurement, and the adapter id and execution backend say so.
    assert records[0]["solver_id"] == f"{LFB_ADAPTER}:claude:fixture"
    assert records[0]["execution_backend"] == "container_cli_tools_on"

    labels = tmp_path / "labels.jsonl"
    labels.write_text(
        "\n".join(
            json.dumps(_label_record(name, dismissed=name != unit_id))
            for name in ("unit-001", "unit-002")
        )
        + "\n",
        encoding="utf-8",
    )
    scores = tmp_path / "scores.json"
    assert (
        run_legalforecast(
            [
                "score",
                "--runs",
                str(lfb_runs),
                "--labels",
                str(labels),
                "--output",
                str(scores),
            ]
        )
        == 0
    )
    summaries = json.loads(scores.read_text(encoding="utf-8"))["summaries"]
    assert len(summaries) == 1
    summary = summaries[0]
    assert summary["model_id"] == f"{LFB_ADAPTER}:claude:fixture"
    # The chain ends in a number, not merely in a row that exists. The scored
    # unit's label above is "survives in material respect", so the outcome is
    # 0; a 0.25 forecast against it is a Brier of 0.0625, and the 0.5 base
    # rate over the label file makes that a skill score of 0.75. Both are
    # exact in binary floating point, so the value is pinned rather than
    # bracketed -- a silent change in how the lane's rows reach lfb_brier
    # moves the number and fails here.
    assert summary["unit_count"] == 1
    assert summary["micro_brier"] == 0.0625
    assert summary["macro_brier"] == 0.0625
    assert summary["base_rate"] == 0.5
    assert summary["brier_skill_score"] == 0.75
    unit_score = summary["unit_scores"][0]
    assert unit_score["unit_id"] == unit_id
    assert unit_score["outcome"] == 0
    assert unit_score["probability_fully_dismissed"] == 0.25
    assert unit_score["parser_status"] == "valid"


def test_lfb_release_task_source_requires_an_artifact_root(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="needs artifact_root"):
        _run_multiharness(
            [
                "multiharness",
                "run",
                "--task-source",
                "lfb",
                "--forecast-release",
                str(tmp_path / "forecast-release.json"),
                "--adapter",
                LFB_ADAPTER,
                "--local-cli-manifest",
                str(CONTAINER_MANIFEST / "local-cli-adapter-manifest.json"),
                "--model-key",
                "claude:fixture",
                "--output-dir",
                str(tmp_path / "run"),
            ]
        )


def _lab_manifest_record() -> dict[str, Any]:
    return json.loads(
        (LAB_MANIFEST / "local-cli-adapter-manifest.json").read_text(encoding="utf-8")
    )


def test_committed_lab_manifest_is_self_consistent() -> None:
    """The LAB sibling differs from the LFB manifest only where it must.

    Image digest, argv template and tool posture are reused verbatim -- this
    is the same program under the same fence -- and only the family, the
    scoring mode, the prompt source and the identity change.  The capability
    digest is recomputed over the changed payload rather than copied, which is
    the one way a hand-edited manifest silently stops describing itself.
    """

    lab = _lab_manifest_record()
    lfb = _lane_manifest_record()
    assert lab["capability_digest"] == capability_digest_for(lab)
    assert lab["harness_binding"]["supported_families"] == ["harvey_lab"]
    assert lab["harness_binding"]["supported_scoring_modes"] == ["lab_native"]
    assert lab["task_projection"]["prompt_source"] == "projected_task_instructions"
    assert lab["executable"] == lfb["executable"]
    assert lab["invocation"] == lfb["invocation"]
    assert lab["capabilities"] == lfb["capabilities"]
    assert lab["manifest_id"] != lfb["manifest_id"]


def _docx_bytes() -> bytes:
    """The smallest thing LAB output discovery accepts: real zip magic."""

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types></Types>")
        archive.writestr("word/document.xml", "<w:document></w:document>")
    return buffer.getvalue()


def _evaluator_environment(tmp_path: Path) -> dict[str, str]:
    """Install the fixture LAB judge on a PATH the contained runtime will use."""

    bin_dir = tmp_path / "eval-bin"
    bin_dir.mkdir()
    wrapper = bin_dir / EVALUATOR_COMMAND_NAME
    body = FAKE_EVALUATOR.read_text(encoding="utf-8")
    if body.startswith("#!"):
        body = body.split("\n", 1)[1]
    wrapper.write_text("#!" + sys.executable + "\n" + body, encoding="utf-8")
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '/usr/bin')}",
        "LC_CTYPE": "C.UTF-8",
        "HOME": str(tmp_path / "evaluator-home"),
    }


def _run_lab_row(
    tmp_path: Path,
    fake_container: dict[str, Any],
    output_dir: Path,
) -> tuple[Any, Any]:
    """Run one projected LAB row through the container lane."""

    result, index = projected_lab_layout(tmp_path)
    task = next(
        item
        for item in index.tasks
        if item.metadata["lab_task_id"] == ISSUE_196_LAB_TASK_ID
    )
    fake_container["answer"] = "Drafted the memo into the output directory."
    fake_container["workspace_files"] = {
        f"output/{task.metadata['expected_deliverable']}": _docx_bytes()
    }
    assert (
        _run_multiharness(
            [
                "multiharness",
                "run",
                "--task-source",
                "harvey-lab",
                "--projected-root",
                str(result.solver_root),
                "--adapter",
                LFB_ADAPTER,
                "--local-cli-manifest",
                str(LAB_MANIFEST / "local-cli-adapter-manifest.json"),
                "--auth-profile",
                "fixture-none",
                "--allow-host",
                PROVIDER_HOST,
                "--model-key",
                "claude:fixture",
                "--task-id",
                task.task_id,
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )
    return result, task


def test_container_lane_harvey_lab_leg_scores_through_its_own_evaluator(
    tmp_path: Path, fake_container: dict[str, Any]
) -> None:
    """The LAB leg reaches an authorized native score, and never lfb_brier.

    The harness is told to write ``output/<deliverable>``; discovery seals
    exactly that file; the isolated evaluator reads it beside the
    evaluator-private criteria the solver never saw; and the receipt is
    verified and normalized before any number is written down.  The judge here
    is the fixture judge, so what is proven is the wiring and the bindings --
    not a model's LAB performance.
    """

    output_dir = tmp_path / "run"
    result, task = _run_lab_row(tmp_path, fake_container, output_dir)

    # The harness was told where the scored file goes, and the container was
    # handed the projected instructions rather than any private store.
    prompt = _scored_spec(fake_container).harness_argv
    assert any("output/" in argument for argument in prompt)
    assert any(
        str(task.metadata["expected_deliverable"]) in argument for argument in prompt
    )

    scores = score_harness_lane_lab_run(
        run_dir=output_dir,
        projection_root=result.solver_root,
        evaluator_private_root=result.evaluator_private_root,
        work_root=tmp_path / "lab-scoring",
        signer=LAB_ISSUER_KEY.sign,
        issuer_public_key=LAB_ISSUER_KEY.public_key(),
        execution_service=LocalCliExecutionService(
            parent_env=_evaluator_environment(tmp_path)
        ),
    )
    assert len(scores) == 1
    assert scores[0].scored

    records = [
        json.loads(line)
        for line in (output_dir / "lab" / "scores.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert len(records) == 1
    record = records[0]
    assert record["scoring_mode"] == "lab_native"
    assert record["metric_id"] == "harvey-lab-binary-all-pass-v1"
    assert record["lab_task_id"] == ISSUE_196_LAB_TASK_ID
    assert record["solver_id"] == (f"{LFB_ADAPTER}-harvey-lab:claude:fixture")
    assert record["execution_backend"] == "container_cli_tools_on"
    assert record["score"]["score_value"] == 1
    assert record["score"]["n_passed"] == record["score"]["n_criteria"] == 23
    assert record["unscored_reason"] is None
    validate_public_record(record, "harness lane LAB score")

    # A LAB score cannot be mistaken for an MTD forecast: none of the fields an
    # lfb_brier row is made of exist here, and the LFB scorer's input file was
    # never written by this run.
    assert not {
        "probability_fully_dismissed",
        "predictions",
        "unit_id",
        "raw_output",
        "parser_output",
        "required_unit_ids",
    } & set(record)
    assert not (output_dir / "lfb" / "runs.jsonl").exists()

    # The gold criteria stayed on the evaluator side of the projection.
    staged = _scored_spec(fake_container).workspace
    assert not list(staged.rglob("task.json"))
    assert not list(staged.rglob("gold-answers.json"))


def test_lab_scoring_refuses_a_run_with_no_lab_rows(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    (run_dir / "lab").mkdir(parents=True)
    with pytest.raises(LabScoringError, match="no Harvey LAB rows to score"):
        score_harness_lane_lab_run(
            run_dir=run_dir,
            projection_root=tmp_path / "projected",
            evaluator_private_root=tmp_path / "private",
            work_root=tmp_path / "lab-scoring",
            signer=LAB_ISSUER_KEY.sign,
            issuer_public_key=LAB_ISSUER_KEY.public_key(),
            execution_service=LocalCliExecutionService(),
        )


def test_lab_scoring_refuses_a_missing_deliverable(
    tmp_path: Path, fake_container: dict[str, Any]
) -> None:
    """A harness that answered in prose alone produces no score, not a zero."""

    output_dir = tmp_path / "run"
    result, _task = _run_lab_row(tmp_path, fake_container, output_dir)
    deliverable = next((output_dir / "rows").rglob("container-workspace/output/*.docx"))
    deliverable.unlink()

    with pytest.raises(Exception, match="missing required deliverable"):
        score_harness_lane_lab_run(
            run_dir=output_dir,
            projection_root=result.solver_root,
            evaluator_private_root=result.evaluator_private_root,
            work_root=tmp_path / "lab-scoring",
            signer=LAB_ISSUER_KEY.sign,
            issuer_public_key=LAB_ISSUER_KEY.public_key(),
            execution_service=LocalCliExecutionService(
                parent_env=_evaluator_environment(tmp_path)
            ),
        )


def test_a_failed_lab_row_is_recorded_unscored_rather_than_dropped(
    tmp_path: Path,
) -> None:
    """A row that did not succeed keeps its place in the denominator.

    Dropping it would quietly raise the pass rate, so it is written with a
    null score and the status that explains it.
    """

    result, index = projected_lab_layout(tmp_path)
    task = next(
        item
        for item in index.tasks
        if item.metadata["lab_task_id"] == ISSUE_196_LAB_TASK_ID
    )
    run_dir = tmp_path / "run"
    (run_dir / "lab").mkdir(parents=True)
    (run_dir / "lab" / "task-results.jsonl").write_text(
        json.dumps(
            {
                "row_id": "row-crashed",
                "task_id": task.task_id,
                "adapter_id": f"{LFB_ADAPTER}-harvey-lab",
                "adapter_version": "1.0.0",
                "model_key": "claude:fixture",
                "request_sha256": "sha256:" + "0" * 64,
                "result": {"status": "failed"},
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    scores = score_harness_lane_lab_run(
        run_dir=run_dir,
        projection_root=result.solver_root,
        evaluator_private_root=result.evaluator_private_root,
        work_root=tmp_path / "lab-scoring",
        signer=LAB_ISSUER_KEY.sign,
        issuer_public_key=LAB_ISSUER_KEY.public_key(),
        execution_service=LocalCliExecutionService(
            parent_env=_evaluator_environment(tmp_path)
        ),
    )
    assert len(scores) == 1
    assert not scores[0].scored

    record = json.loads(
        (run_dir / "lab" / "scores.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    assert record["score"] is None
    assert record["unscored_reason"] == "failed"
    assert record["scoring_mode"] == "lab_native"
    validate_public_record(record, "harness lane LAB score")
    assert not (tmp_path / "lab-scoring" / "row-crashed").exists()
