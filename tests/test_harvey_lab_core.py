"""Contract tests; deterministic runtimes below are not paid provider evidence."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from legalforecast._json_io import write_json_object
from legalforecast.multiharness.harvey_lab import core_runtime
from legalforecast.multiharness.harvey_lab.core_bridge import (
    LabCoreRequest,
    normalize_scores,
    run_lab_core,
)
from legalforecast.multiharness.harvey_lab.core_cli import register
from legalforecast.multiharness.harvey_lab.core_runtime import (
    EVALUATE_MODULE,
    PACKAGE_VERSION,
    RUN_MODULE,
    UPSTREAM_COMMIT,
    UPSTREAM_TREE,
    LabCoreError,
    LabCoreRuntime,
)


def _request() -> LabCoreRequest:
    return LabCoreRequest(
        task_id="harvey_lab:example/task",
        model="openai/gpt-example",
        judge_model="judge-example",
        run_id="measurement-1",
        max_turns=3,
        sandbox_image="sha256:" + "a" * 64,
    )


def _scores(request: LabCoreRequest) -> dict[str, object]:
    return {
        "run_id": request.upstream_run_id,
        "task": request.upstream_task_id,
        "judge_model": request.judge_model,
        "n_criteria": 2,
        "n_passed": 1,
        "all_pass": False,
        "score": 0.0,
        "max_score": 1.0,
        "criteria_results": [
            {"id": "C-001", "verdict": "pass", "reasoning": "PRIVATE_REASON"},
            {"id": "C-002", "verdict": "fail", "reasoning": "PRIVATE_REASON"},
        ],
    }


class RecordingRuntime(LabCoreRuntime):
    """Replace upstream process execution only; use real materialization/scoring."""

    calls: list[tuple[str, tuple[str, ...]]]
    sabotage: str = ""

    def verify(self, private_root: Path) -> dict[str, str]:
        return {"commit": UPSTREAM_COMMIT, "package_version": PACKAGE_VERSION}

    def probe(self, private_root: Path) -> dict[str, str]:
        return self.verify(private_root)

    def prepare_sandbox(self, private_root: Path, image: str) -> None:
        assert image == _request().sandbox_image

    def invoke(
        self,
        module: str,
        arguments: tuple[str, ...],
        *,
        private_root: Path,
        lab_root: Path,
        phase: str,
        timeout: float,
        provider_env: tuple[str, ...] = (),
    ) -> None:
        self.calls.append((module, arguments))
        assert "--lab-root" not in arguments and "--output-dir" not in arguments
        run_id = arguments[arguments.index("--run-id") + 1]
        task = arguments[arguments.index("--task") + 1]
        root = lab_root / "results" / run_id
        if module == RUN_MODULE:
            output = root / "output"
            output.mkdir(parents=True)
            (output / "answer.docx").write_bytes(b"fixture work product")
            record: dict[str, object] = {
                "task": task,
                "model": _request().model,
                "run_id": run_id,
                "finished_cleanly": True,
            }
            if self.sabotage == "identity":
                record["task"] = "wrong/task"
            if self.sabotage == "unfinished":
                record["finished_cleanly"] = False
            if self.sabotage == "symlink":
                (output / "answer.docx").unlink()
                (output / "answer.docx").symlink_to(self.source_root / "LICENSE")
            write_json_object(root / "config.json", record)
            write_json_object(root / "metrics.json", record)
        else:
            assert module == EVALUATE_MODULE
            assert arguments[-4:] == ("--judges", "judge-example", "--parallel", "1")
            if self.sabotage == "mutation":
                (root / "output" / "answer.docx").write_bytes(b"changed")
            if self.sabotage == "extra-output":
                (root / "output" / "unexpected.txt").write_text("extra")
            scores = _scores(_request())
            if self.sabotage == "malformed":
                scores["criteria_results"] = []
            write_json_object(root / "scores.json", scores)


def _runtime(tmp_path: Path, sabotage: str = "") -> RecordingRuntime:
    source = tmp_path / "source"
    task = source / "tasks" / "example" / "task"
    (task / "documents").mkdir(parents=True)
    (source / "LICENSE").write_text("MIT fixture notice")
    (task / "documents" / "source.txt").write_text("source document")
    write_json_object(
        task / "task.json",
        {
            "title": "Example",
            "instructions": "Write answer.docx",
            "deliverables": {"answer.docx": "answer.docx"},
            "criteria": [
                {"id": "C-001", "match_criteria": "PRIVATE_RUBRIC"},
                {"id": "C-002", "match_criteria": "PRIVATE_RUBRIC"},
            ],
        },
    )
    runtime = RecordingRuntime(source, Path("unused-python"))
    object.__setattr__(runtime, "calls", [])
    object.__setattr__(runtime, "sabotage", sabotage)
    return runtime


def test_bridge_runs_supported_two_command_contract_and_public_projection(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    result = run_lab_core(runtime, _request(), tmp_path / "run")
    assert [module for module, _argv in runtime.calls] == [RUN_MODULE, EVALUATE_MODULE]
    assert result["score"] == 0
    assert result["criterion_pass_rate"] == 0.5
    assert result["task_id"] == "harvey_lab:example/task"
    assert result["upstream_run_id"] == _request().upstream_run_id
    public = tmp_path / "run" / "public"
    public_text = (public / "scores.json").read_text()
    assert "PRIVATE_RUBRIC" not in public_text and "PRIVATE_REASON" not in public_text
    assert "MIT fixture notice" in (public / "NOTICE.txt").read_text()
    assert (
        tmp_path
        / "run"
        / "private"
        / "lab"
        / "tasks"
        / "example"
        / "task"
        / "documents"
        / "source.txt"
    ).read_text() == "source document"


@pytest.mark.parametrize(
    "sabotage",
    ["identity", "unfinished", "symlink", "mutation", "extra-output", "malformed"],
)
def test_bridge_refuses_invalid_or_changed_outputs(
    tmp_path: Path, sabotage: str
) -> None:
    runtime = _runtime(tmp_path, sabotage)
    with pytest.raises(LabCoreError):
        run_lab_core(runtime, _request(), tmp_path / "run")
    assert not (tmp_path / "run" / "public").exists()
    if sabotage in {"identity", "unfinished", "symlink"}:
        assert (
            len(runtime.calls) == 1
        )  # no judge/provider stage for invalid solver output


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("run_id", "other"),
        ("task", "other/task"),
        ("judge_model", "other"),
        ("n_criteria", 1),
        ("n_passed", True),
        ("all_pass", True),
        ("score", 1.0),
        ("max_score", True),
        ("criteria_results", [{"id": "C-001", "verdict": "pass"}] * 2),
        ("criteria_results", [{"id": "C-001", "verdict": "error"}]),
    ],
)
def test_normalization_rejects_malformed_or_misattributed_scores(
    key: str, value: object
) -> None:
    scores = _scores(_request())
    scores[key] = value
    with pytest.raises(LabCoreError):
        normalize_scores(scores, _request(), ("C-001", "C-002"))


def test_run_identity_is_deterministic_and_safe() -> None:
    request = _request()
    assert (
        replace(request, task_id="example/task").upstream_run_id
        == request.upstream_run_id
    )
    assert "/" not in request.upstream_run_id
    assert (
        replace(request, model="other/model").upstream_run_id != request.upstream_run_id
    )
    with pytest.raises(ValueError):
        replace(request, task_id="../escape")
    with pytest.raises(LabCoreError):
        replace(request, provider_env=("DATABASE_PASSWORD",))


def test_source_drift_is_refused_before_package_execution(tmp_path: Path) -> None:
    runtime = LabCoreRuntime(Path(__file__).resolve().parents[1], Path("never-launch"))
    with pytest.raises(LabCoreError, match=r"supported v1\.1\.0 pin"):
        runtime.verify(tmp_path)


@pytest.mark.parametrize("defect", ["version", "bytes", "malformed"])
def test_runtime_rejects_incompatible_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, defect: str
) -> None:
    source, installed = tmp_path / "source", tmp_path / "installed"
    (source / "lab_core").mkdir(parents=True)
    installed.mkdir()
    (source / "lab_core" / "__init__.py").write_text("# pinned package\n")
    (installed / "__init__.py").write_text(
        "# modified package\n" if defect == "bytes" else "# pinned package\n"
    )
    stdout = json.dumps(
        {
            "version": "1.0.0" if defect == "version" else PACKAGE_VERSION,
            "root": str(installed),
        }
    )
    if defect == "malformed":
        stdout = "not JSON"

    def command(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if argv[0] == "git":
            stdout_value = {
                "HEAD": UPSTREAM_COMMIT,
                "HEAD^{tree}": UPSTREAM_TREE,
                "--show-toplevel": str(source),
                "--untracked-files=all": "",
            }[argv[-1]]
        else:
            stdout_value = stdout
        return subprocess.CompletedProcess(argv, 0, stdout_value, "")

    monkeypatch.setattr(core_runtime.subprocess, "run", command)
    runtime = LabCoreRuntime(source, Path("unused-python"))
    with pytest.raises(LabCoreError):
        runtime.verify(tmp_path)


def test_cli_exposes_explicit_source_python_and_judge_contract() -> None:
    parser = argparse.ArgumentParser()
    register(parser.add_subparsers())
    args = parser.parse_args(
        [
            "harvey-lab",
            "run",
            "--source-root",
            "upstream",
            "--python",
            "env/bin/python",
            "--output-dir",
            "output",
            "--task-id",
            "example/task",
            "--model",
            "openai/model",
            "--judge-model",
            "claude-example",
            "--run-id",
            "one",
            "--max-turns",
            "4",
            "--sandbox-image",
            "image",
        ]
    )
    assert args.judge_model == "claude-example"
    assert args.provider_env == []


def test_native_command_is_wired_into_installed_cli() -> None:
    result = subprocess.run(
        [
            str(Path(sys.executable).with_name("legalforecast")),
            "harvey-lab",
            "run",
            "--help",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "--judge-model" in result.stdout and "--sandbox-image" in result.stdout


def _real_runtime() -> LabCoreRuntime:
    source, python = os.environ.get("LAB_CORE_ROOT"), os.environ.get("LAB_CORE_PYTHON")
    if not source or not python:
        pytest.skip("set LAB_CORE_ROOT and LAB_CORE_PYTHON for the real package probe")
    return LabCoreRuntime(Path(source), Path(python))


def test_real_pinned_package_cli_probe_has_no_provider_grants(tmp_path: Path) -> None:
    runtime = _real_runtime()
    observed = runtime.probe(tmp_path)
    assert observed["commit"] == UPSTREAM_COMMIT
    assert observed["package_version"] == PACKAGE_VERSION
    assert not any(name.endswith("_API_KEY") for name in runtime.environment(tmp_path))
    assert "--judges" in (tmp_path / "run_eval-help.stdout").read_text()


def test_real_native_sandbox_uses_prepared_image_without_credentials(
    tmp_path: Path,
) -> None:
    runtime = _real_runtime()
    image = os.environ.get("LAB_CORE_SANDBOX_IMAGE")
    if not image:
        pytest.skip("set LAB_CORE_SANDBOX_IMAGE to an existing immutable image ID")
    runtime.verify(tmp_path)
    runtime.prepare_sandbox(tmp_path, image)
    environment = runtime.sandbox_environment(tmp_path)
    environment["PROBE_IMAGE"] = image
    script = """
import os
from pathlib import Path
from lab_core.sandbox.sandbox import Sandbox
assert not any(k.endswith("_API_KEY") for k in os.environ)
with Sandbox(Path("docs"), Path("out"), Path("work"),
             image=os.environ["PROBE_IMAGE"]) as sandbox:
    result = sandbox.exec("printf bridge-sandbox-probe")
    assert result.returncode == 0, result
    assert result.stdout == "bridge-sandbox-probe", result
print("native rootless sandbox passed")
"""
    result = subprocess.run(
        [str(runtime.python), "-B", "-I", "-c", script],
        env=environment,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "native rootless sandbox passed" in result.stdout


def test_real_pinned_package_evaluator_normalizes_without_provider_calls(
    tmp_path: Path,
) -> None:
    runtime = _real_runtime()
    runtime.verify(tmp_path)
    task = "employment-labor/identify-issues-in-counterparty-motion-brief"
    task_root = runtime.source_root / "tasks" / task
    record = json.loads((task_root / "task.json").read_text())
    request = replace(
        _request(), task_id=task, judge_model="deterministic-offline-stub"
    )
    output = tmp_path / "results" / request.upstream_run_id / "output"
    output.mkdir(parents=True)
    source = next((task_root / "documents").glob("*.docx"))
    for name in record["deliverables"].values():
        shutil.copyfile(source, output / name)
    script = """
import json, os
from pathlib import Path
import lab_core.evaluation.run_eval as evaluator
class OfflineJudge:
    model = "deterministic-offline-stub"
    def evaluate_from_file(self, *, prompt_name, variables):
        assert prompt_name == "rubric_criterion"
        assert variables["agent_output"]
        assert "(error reading" not in variables["agent_output"]
        return {"verdict": "pass", "reasoning": "offline boundary probe"}
assert not any(k.endswith("_API_KEY") for k in os.environ)
evaluator.RESULTS_DIR = Path(os.environ["PROBE_RESULTS"])
scores = evaluator.evaluate_run(
    os.environ["PROBE_RUN"], os.environ["PROBE_TASK"], OfflineJudge(), parallel=1
)
print(json.dumps(scores))
"""
    environment = runtime.environment(tmp_path)
    environment.update(
        {
            "LAB_ROOT": str(runtime.source_root),
            "PROBE_RESULTS": str(tmp_path / "results"),
            "PROBE_RUN": request.upstream_run_id,
            "PROBE_TASK": task,
        }
    )
    result = subprocess.run(
        [str(runtime.python), "-B", "-I", "-c", script],
        env=environment,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    normalized = normalize_scores(
        json.loads(result.stdout), request, tuple(c["id"] for c in record["criteria"])
    )
    assert normalized["score"] == 1
    assert normalized["n_criteria"] == len(record["criteria"])
