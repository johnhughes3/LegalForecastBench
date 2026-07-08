from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from legalforecast.multiharness import harvey_lab_adapter as lab_adapter_module
from legalforecast.multiharness.harvey_lab_adapter import (
    HarveyLabCliAdapter,
    HarveyLabCliAdapterError,
)
from legalforecast.multiharness.sandbox import sandbox_policy
from legalforecast.multiharness.spec import CanonicalTask, RunRequest
from legalforecast.multiharness.task_loaders import HarveyLabTaskLoader


def test_harvey_lab_cli_adapter_runs_fixture_and_keeps_private_outputs(
    tmp_path: Path,
) -> None:
    lab_root = _lab_root(tmp_path)
    command = _lab_command(tmp_path)
    adapter = HarveyLabCliAdapter(
        lab_command=(sys.executable, str(command)),
        lab_root=lab_root,
    )
    task = (
        HarveyLabTaskLoader(
            lab_root,
            suite_version="fixture-lab",
        )
        .load_task_index()
        .tasks[0]
    )
    workspace = tmp_path / "workspace"

    capabilities = adapter.capabilities(workspace / "capabilities")
    result = adapter.run(_request(adapter, task), workspace)

    assert capabilities.supported_families == ("harvey_lab",)
    lab_capabilities = json.loads(
        (workspace / "capabilities" / "lab-command-capabilities.json").read_text(
            encoding="utf-8"
        )
    )
    assert lab_capabilities["lab_commit"] == "unknown"
    assert "--lab-root" in lab_capabilities["supported_flags"]
    assert "--output-dir" in lab_capabilities["supported_flags"]
    assert result.status == "succeeded"
    assert result.public_summary["criterion_count"] == 2
    assert result.public_summary["mean_normalized_score"] == 0.75
    assert (workspace / "lab-task-results.jsonl").is_file()
    artifact_by_id = {artifact.artifact_id: artifact for artifact in result.artifacts}
    assert artifact_by_id["lab-scores"].public is True
    assert artifact_by_id["private:report.html"].public is False
    assert artifact_by_id["private:transcripts/run.txt"].public is False
    assert "SECRET_TRANSCRIPT" not in json.dumps(result.to_record(), sort_keys=True)


def test_harvey_lab_adapter_reports_missing_required_flags(tmp_path: Path) -> None:
    lab_root = _lab_root(tmp_path)
    command = _lab_command(tmp_path, include_output_flag=False)
    adapter = HarveyLabCliAdapter(
        lab_command=(sys.executable, str(command)),
        lab_root=lab_root,
    )
    task = HarveyLabTaskLoader(lab_root).load_task_index().tasks[0]

    with pytest.raises(HarveyLabCliAdapterError, match="--output-dir"):
        adapter.run(_request(adapter, task), tmp_path / "workspace")


def test_harvey_lab_adapter_validates_lab_root(tmp_path: Path) -> None:
    adapter = HarveyLabCliAdapter(
        lab_command=(sys.executable, str(_lab_command(tmp_path))),
        lab_root=tmp_path / "missing",
    )

    with pytest.raises(HarveyLabCliAdapterError, match="LAB root does not exist"):
        adapter.capabilities(tmp_path / "workspace")


def test_harvey_lab_adapter_maps_missing_command_to_domain_error(
    tmp_path: Path,
) -> None:
    adapter = HarveyLabCliAdapter(
        lab_command=("missing-harvey-lab-command-for-test",),
        lab_root=_lab_root(tmp_path),
    )

    with pytest.raises(HarveyLabCliAdapterError, match="could not start"):
        adapter.capabilities(tmp_path / "workspace")


@pytest.mark.parametrize("failure", ["timeout", "oserror"])
def test_lab_commit_returns_unknown_when_git_probe_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    def fail_git_probe(
        *_args: object,
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        if failure == "timeout":
            raise subprocess.TimeoutExpired(cmd=("git",), timeout=10)
        raise OSError("git unavailable")

    monkeypatch.setattr(lab_adapter_module.subprocess, "run", fail_git_probe)

    assert lab_adapter_module._lab_commit(tmp_path) == "unknown"


def _request(adapter: HarveyLabCliAdapter, task: CanonicalTask) -> RunRequest:
    return RunRequest(
        request_id="lab-request-1",
        task=task,
        adapter=adapter.manifest,
        model_key="fixture-model",
        sandbox_policy=sandbox_policy(
            policy_id="fixture",
            backend="docker",
            image="python:3.12-slim",
            mounts=(),
            timeout_seconds=30,
        ),
        request_sha256="sha256:" + "b" * 64,
    )


def _lab_root(tmp_path: Path) -> Path:
    lab_root = tmp_path / "lab"
    task_dir = lab_root / "tasks" / "corporate" / "merger"
    docs_dir = task_dir / "documents"
    docs_dir.mkdir(parents=True)
    (task_dir / "task.json").write_text(
        json.dumps(
            {
                "id": "merger-review",
                "metadata": {
                    "module": "corporate",
                    "practice_area": "m-and-a",
                },
            }
        ),
        encoding="utf-8",
    )
    (docs_dir / "agreement.md").write_text("agreement text", encoding="utf-8")
    return lab_root


def _lab_command(tmp_path: Path, *, include_output_flag: bool = True) -> Path:
    script = tmp_path / f"lab_command_{include_output_flag}.py"
    help_flags = "--lab-root --output-dir" if include_output_flag else "--lab-root"
    script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "from __future__ import annotations",
                "import argparse, json",
                f"HELP_FLAGS = {help_flags!r}",
                "parser = argparse.ArgumentParser(add_help=False)",
                "parser.add_argument('--help', action='store_true')",
                "parser.add_argument('--lab-root')",
                "parser.add_argument('--output-dir')",
                "args = parser.parse_args()",
                "if args.help:",
                "    print('usage: harness.run ' + HELP_FLAGS)",
                "    raise SystemExit(0)",
                "out = args.output_dir",
                "import pathlib",
                "output = pathlib.Path(out)",
                "output.mkdir(parents=True, exist_ok=True)",
                "(output / 'transcripts').mkdir(exist_ok=True)",
                "(output / 'report.html').write_text(",
                "    'SECRET_REPORT', encoding='utf-8'",
                ")",
                "(output / 'transcripts' / 'run.txt').write_text(",
                "    'SECRET_TRANSCRIPT', encoding='utf-8'",
                ")",
                "scores = {'scores': [",
                "  {'criterion_id': 'accuracy', 'score': 0.8, 'max_score': 1.0},",
                "  {'criterion_id': 'citation', 'score': 0.7, 'max_score': 1.0},",
                "]}",
                "(output / 'scores.json').write_text(",
                "    json.dumps(scores), encoding='utf-8'",
                ")",
            ]
        ),
        encoding="utf-8",
    )
    return script
