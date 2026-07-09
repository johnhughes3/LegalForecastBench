# pyright: reportPrivateUsage=false

from __future__ import annotations

import json
import os
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
        (
            workspace
            / "capabilities"
            / "private-logs"
            / "lab-command-capabilities.json"
        ).read_text(encoding="utf-8")
    )
    assert lab_capabilities["lab_commit"] != "unknown"
    assert lab_capabilities["lab_source_sha256"].startswith("sha256:")
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


def test_harvey_lab_capability_hash_ignores_local_paths(
    tmp_path: Path,
) -> None:
    first_root = _lab_root(tmp_path / "first")
    second_root = _clone_lab_root(first_root, tmp_path / "second")
    first_adapter = HarveyLabCliAdapter(
        lab_command=(sys.executable, str(_lab_command(tmp_path / "first"))),
        lab_root=first_root,
    )
    second_adapter = HarveyLabCliAdapter(
        lab_command=(sys.executable, str(_lab_command(tmp_path / "second"))),
        lab_root=second_root,
    )

    first = first_adapter.capabilities(tmp_path / "first-workspace")
    second = second_adapter.capabilities(tmp_path / "second-workspace")

    assert first.capabilities_sha256 == second.capabilities_sha256
    first_probe = json.loads(
        (
            tmp_path
            / "first-workspace"
            / "private-logs"
            / "lab-command-capabilities.json"
        ).read_text(encoding="utf-8")
    )
    second_probe = json.loads(
        (
            tmp_path
            / "second-workspace"
            / "private-logs"
            / "lab-command-capabilities.json"
        ).read_text(encoding="utf-8")
    )
    assert first_probe["lab_root"] != second_probe["lab_root"]
    assert first_probe["evaluation_command"] != second_probe["evaluation_command"]
    assert first_probe["lab_source_sha256"] == second_probe["lab_source_sha256"]
    compatibility_json = json.dumps(
        first_adapter.command_capabilities(
            tmp_path / "compatibility-probe"
        ).to_compatibility_record(),
        sort_keys=True,
    )
    assert first_root.as_posix() not in compatibility_json
    assert str(first_adapter.lab_command[1]) not in compatibility_json


def test_harvey_lab_dirty_overlay_changes_source_identity(
    tmp_path: Path,
) -> None:
    first_root = _lab_root(tmp_path / "first")
    second_root = _clone_lab_root(first_root, tmp_path / "second")
    first_adapter = HarveyLabCliAdapter(
        lab_command=(sys.executable, str(_lab_command(tmp_path / "first"))),
        lab_root=first_root,
    )
    second_adapter = HarveyLabCliAdapter(
        lab_command=(sys.executable, str(_lab_command(tmp_path / "second"))),
        lab_root=second_root,
    )

    first = first_adapter.capabilities(tmp_path / "first-workspace")
    matching = second_adapter.capabilities(tmp_path / "matching-workspace")
    (second_root / "tasks/corporate/merger/documents/agreement.md").write_text(
        "different agreement text",
        encoding="utf-8",
    )
    changed = HarveyLabCliAdapter(
        lab_command=second_adapter.lab_command,
        lab_root=second_root,
    ).capabilities(tmp_path / "changed-workspace")
    (first_root / "tasks/corporate/merger/documents/agreement.md").write_text(
        "different agreement text",
        encoding="utf-8",
    )
    matching_dirty = HarveyLabCliAdapter(
        lab_command=first_adapter.lab_command,
        lab_root=first_root,
    ).capabilities(tmp_path / "matching-dirty-workspace")

    assert first.capabilities_sha256 == matching.capabilities_sha256
    assert first.capabilities_sha256 != changed.capabilities_sha256
    assert matching_dirty.capabilities_sha256 == changed.capabilities_sha256


def test_harvey_lab_capability_hash_distinguishes_commits(
    tmp_path: Path,
) -> None:
    first_root = _lab_root(tmp_path / "first")
    second_root = _clone_lab_root(first_root, tmp_path / "second")
    (second_root / "harness.py").write_text("VERSION = 2\n", encoding="utf-8")
    _commit_all(second_root, "change harness")
    first_adapter = HarveyLabCliAdapter(
        lab_command=(sys.executable, str(_lab_command(tmp_path / "first"))),
        lab_root=first_root,
    )
    second_adapter = HarveyLabCliAdapter(
        lab_command=(sys.executable, str(_lab_command(tmp_path / "second"))),
        lab_root=second_root,
    )

    first = first_adapter.capabilities(tmp_path / "first-workspace")
    second = second_adapter.capabilities(tmp_path / "second-workspace")

    assert first.capabilities_sha256 != second.capabilities_sha256


def test_harvey_lab_capability_hash_binds_command_implementation(
    tmp_path: Path,
) -> None:
    first_root = _lab_root(tmp_path / "first")
    second_root = _clone_lab_root(first_root, tmp_path / "second")
    first_command = _lab_command(tmp_path / "first")
    second_command = _lab_command(tmp_path / "second")
    second_command.write_text(
        second_command.read_text(encoding="utf-8").replace(
            "'score': 0.8", "'score': 0.1"
        ),
        encoding="utf-8",
    )

    first = HarveyLabCliAdapter(
        lab_command=(sys.executable, str(first_command)),
        lab_root=first_root,
    ).capabilities(tmp_path / "first-workspace")
    second = HarveyLabCliAdapter(
        lab_command=(sys.executable, str(second_command)),
        lab_root=second_root,
    ).capabilities(tmp_path / "second-workspace")

    assert first.capabilities_sha256 != second.capabilities_sha256


def test_harvey_lab_rejects_capability_mutation_after_planning(
    tmp_path: Path,
) -> None:
    lab_root = _lab_root(tmp_path)
    command = _lab_command(tmp_path)
    adapter = HarveyLabCliAdapter(
        lab_command=(sys.executable, str(command)),
        lab_root=lab_root,
    )
    task = HarveyLabTaskLoader(lab_root).load_task_index().tasks[0]
    adapter.capabilities(tmp_path / "planned-capabilities")
    command.write_text(
        command.read_text(encoding="utf-8").replace("'score': 0.8", "'score': 0.1"),
        encoding="utf-8",
    )

    with pytest.raises(HarveyLabCliAdapterError, match="changed after run planning"):
        adapter.run(_request(adapter, task), tmp_path / "workspace")


def test_harvey_lab_rejects_source_mutation_after_planning(tmp_path: Path) -> None:
    lab_root = _lab_root(tmp_path)
    command = _lab_command(tmp_path)
    adapter = HarveyLabCliAdapter(
        lab_command=(sys.executable, str(command)),
        lab_root=lab_root,
    )
    task = HarveyLabTaskLoader(lab_root).load_task_index().tasks[0]
    adapter.capabilities(tmp_path / "planned-capabilities")
    (lab_root / "harness.py").write_text("VERSION = 2\n", encoding="utf-8")

    with pytest.raises(HarveyLabCliAdapterError, match="changed after run planning"):
        adapter.run(_request(adapter, task), tmp_path / "workspace")


def test_harvey_lab_rejects_changed_task_artifact(tmp_path: Path) -> None:
    lab_root = _lab_root(tmp_path)
    command = _lab_command(tmp_path)
    adapter = HarveyLabCliAdapter(
        lab_command=(sys.executable, str(command)),
        lab_root=lab_root,
    )
    task = HarveyLabTaskLoader(lab_root).load_task_index().tasks[0]
    (lab_root / "tasks/corporate/merger/documents/agreement.md").write_text(
        "changed after task indexing",
        encoding="utf-8",
    )

    workspace = tmp_path / "workspace"
    with pytest.raises(HarveyLabCliAdapterError, match="artifact hash mismatch"):
        adapter.run(_request(adapter, task), workspace)

    assert not (
        workspace / "lab-root/tasks/corporate/merger/documents/agreement.md"
    ).exists()


def test_copy_verified_artifact_removes_partial_destination_after_read_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.bin"
    destination = tmp_path / "destination.bin"
    original_open = Path.open

    class FailingSource:
        def __init__(self) -> None:
            self._read_count = 0

        def __enter__(self) -> FailingSource:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self, _size: int) -> bytes:
            self._read_count += 1
            if self._read_count == 1:
                return b"partial"
            raise OSError("fixture read failure")

    def open_with_read_failure(
        path: Path,
        mode: str = "r",
        *args: object,
        **kwargs: object,
    ) -> object:
        if path == source and mode == "rb":
            return FailingSource()
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_with_read_failure)

    with pytest.raises(
        HarveyLabCliAdapterError, match="could not materialize"
    ) as error:
        lab_adapter_module._copy_verified_artifact(
            source,
            destination,
            expected_sha256="0" * 64,
            expected_size=None,
            artifact_path="artifact.bin",
        )

    assert isinstance(error.value.__cause__, OSError)
    assert not destination.exists()


def test_copy_verified_artifact_preserves_preexisting_destination(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.bin"
    destination = tmp_path / "destination.bin"
    source.write_bytes(b"new payload")
    destination.write_bytes(b"trusted payload")

    with pytest.raises(
        HarveyLabCliAdapterError, match="could not materialize"
    ) as error:
        lab_adapter_module._copy_verified_artifact(
            source,
            destination,
            expected_sha256="0" * 64,
            expected_size=None,
            artifact_path="artifact.bin",
        )

    assert isinstance(error.value.__cause__, FileExistsError)
    assert destination.read_bytes() == b"trusted payload"


def test_harvey_lab_rejects_destination_parent_symlink(tmp_path: Path) -> None:
    lab_root = _lab_root(tmp_path)
    command = _lab_command(tmp_path)
    adapter = HarveyLabCliAdapter(
        lab_command=(sys.executable, str(command)),
        lab_root=lab_root,
    )
    task = HarveyLabTaskLoader(lab_root).load_task_index().tasks[0]
    workspace = tmp_path / "workspace"
    materialized_root = workspace / "lab-root"
    materialized_root.mkdir(parents=True)
    external = tmp_path / "external"
    external.mkdir()
    (materialized_root / "tasks").symlink_to(external, target_is_directory=True)

    with pytest.raises(HarveyLabCliAdapterError, match="contains a symlink"):
        adapter.run(_request(adapter, task), workspace)

    assert list(external.iterdir()) == []


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
def test_lab_identity_rejects_git_probe_failures(
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

    with pytest.raises(HarveyLabCliAdapterError, match="inspect the LAB Git"):
        lab_adapter_module._lab_source_identity(tmp_path)


def test_lab_source_identity_supports_nested_and_dirty_git_roots(
    tmp_path: Path,
) -> None:
    parent = tmp_path / "parent"
    nested_root = _lab_root(parent, initialize_git=False)
    _init_git_repository(parent)
    clean_commit, clean_sha256 = lab_adapter_module._lab_source_identity(nested_root)

    (nested_root / "tasks/corporate/merger/documents/agreement.md").write_text(
        "dirty agreement",
        encoding="utf-8",
    )
    dirty_commit, dirty_sha256 = lab_adapter_module._lab_source_identity(nested_root)

    assert clean_commit == dirty_commit
    assert clean_sha256 != dirty_sha256


def test_lab_source_identity_distinguishes_nested_subtrees(tmp_path: Path) -> None:
    parent = tmp_path / "parent"
    first_root = _lab_root(parent / "first", initialize_git=False)
    second_root = _lab_root(parent / "second", initialize_git=False)
    (second_root / "tasks/corporate/merger/documents/agreement.md").write_text(
        "different subtree",
        encoding="utf-8",
    )
    _init_git_repository(parent)

    first_commit, first_sha256 = lab_adapter_module._lab_source_identity(first_root)
    second_commit, second_sha256 = lab_adapter_module._lab_source_identity(second_root)

    assert first_commit == second_commit
    assert first_sha256 != second_sha256


def test_clean_lab_source_identity_does_not_rehash_tracked_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lab_root = _lab_root(tmp_path)

    def fail_file_hash(_path: Path) -> str:
        raise AssertionError("clean tracked files should be identified by Git tree")

    monkeypatch.setattr(lab_adapter_module, "_file_sha256", fail_file_hash)

    _commit, source_sha256 = lab_adapter_module._lab_source_identity(lab_root)

    assert source_sha256.startswith("sha256:")


def test_lab_source_hash_normalizes_internal_relative_symlinks(
    tmp_path: Path,
) -> None:
    first_root = _lab_root(tmp_path / "first", initialize_git=False)
    (first_root / "harness.py").write_text("VERSION = 1\n", encoding="utf-8")
    (first_root / "runner.py").symlink_to("harness.py")
    _init_git_repository(first_root)
    second_root = _clone_lab_root(first_root, tmp_path / "second")

    assert (
        lab_adapter_module._lab_source_identity(first_root)[1]
        == lab_adapter_module._lab_source_identity(second_root)[1]
    )


def test_lab_source_hash_rejects_external_symlinks(tmp_path: Path) -> None:
    lab_root = _lab_root(tmp_path, initialize_git=False)
    external = tmp_path / "external.py"
    external.write_text("VERSION = 1\n", encoding="utf-8")
    (lab_root / "runner.py").symlink_to("../external.py")
    _init_git_repository(lab_root)

    with pytest.raises(HarveyLabCliAdapterError, match="resolve inside"):
        lab_adapter_module._lab_source_identity(lab_root)


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="requires POSIX FIFOs")
def test_lab_source_hash_rejects_special_file_symlink_targets(tmp_path: Path) -> None:
    lab_root = _lab_root(tmp_path, initialize_git=False)
    (lab_root / ".gitignore").write_text("runtime.pipe\n", encoding="utf-8")
    fifo = lab_root / "runtime.pipe"
    os.mkfifo(fifo)
    (lab_root / "runner.py").symlink_to("runtime.pipe")
    _init_git_repository(lab_root)

    with pytest.raises(HarveyLabCliAdapterError, match="regular files"):
        lab_adapter_module._lab_source_identity(lab_root)


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


def _init_git_repository(path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    _commit_all(path, "fixture")


def _commit_all(path: Path, message: str) -> None:
    subprocess.run(["git", "-C", str(path), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(path),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.com",
            "commit",
            "-qm",
            message,
        ],
        check=True,
    )


def _clone_lab_root(source: Path, destination_parent: Path) -> Path:
    destination_parent.mkdir(parents=True, exist_ok=True)
    destination = destination_parent / "lab"
    subprocess.run(
        ["git", "clone", "-q", str(source), str(destination)],
        check=True,
    )
    return destination


def _lab_root(tmp_path: Path, *, initialize_git: bool = True) -> Path:
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
    if initialize_git:
        _init_git_repository(lab_root)
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
