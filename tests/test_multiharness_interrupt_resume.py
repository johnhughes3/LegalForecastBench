from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import replace
from pathlib import Path

import pytest
from legalforecast.multiharness.adapters import AdapterPreparation
from legalforecast.multiharness.command_adapter import CommandAdapter
from legalforecast.multiharness.run_progress import (
    JOURNAL_FILENAME,
    ResumeRefusedError,
    load_progress_journal,
)
from legalforecast.multiharness.runner import (
    ModelConfig,
    MultiHarnessRunConfig,
    run_multi_harness,
)
from legalforecast.multiharness.sandbox import sandbox_policy
from legalforecast.multiharness.spec import (
    AdapterCapabilities,
    AdapterManifest,
    CanonicalTask,
    ContributorCredit,
    RunRequest,
    RunResult,
    TaskIndex,
)

SHA256 = "sha256:" + "a" * 64
SATURATED_HOST_TIMEOUT_SECONDS = 60
FAST_TASK_ID = "lfb:case-fast:full_packet"
SLOW_TASK_ID = "lfb:case-slow:full_packet"


@pytest.mark.parametrize("cancellation_signal", [signal.SIGINT, signal.SIGTERM])
def test_interrupt_writes_interrupted_receipt_and_kills_process_tree(
    tmp_path: Path,
    cancellation_signal: signal.Signals,
) -> None:
    pid_dir = tmp_path / "process-tree-pids"
    adapter = _interrupt_adapter(tmp_path, pid_dir=pid_dir, slow_task_id=SLOW_TASK_ID)
    output_dir = tmp_path / "run"
    driver_path = _write_driver(tmp_path, output_dir=output_dir, adapter=adapter)
    driver = subprocess.Popen(
        [sys.executable, str(driver_path)],
        cwd=Path.cwd(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _wait_for_process_tree_start(pid_dir)
        group_id = _process_group(int((pid_dir / "parent.pid").read_text()))
        os.kill(driver.pid, cancellation_signal)
        stdout, stderr = driver.communicate(timeout=SATURATED_HOST_TIMEOUT_SECONDS)
    finally:
        if driver.poll() is None:
            driver.kill()
            driver.wait(timeout=SATURATED_HOST_TIMEOUT_SECONDS)

    assert driver.returncode == 130, (stdout, stderr)
    _assert_process_tree_stopped(pid_dir)
    _assert_process_group_stopped(group_id)
    journal = load_progress_journal(output_dir)
    assert journal is not None
    assert journal.status == "interrupted"
    rows = json.loads((output_dir / "selection-manifest.json").read_text())
    assert rows["claim_kind"] == "partial"
    assert "partial" in rows["selection_label"]
    result_dirs = sorted((output_dir / "rows").iterdir())
    statuses = [
        json.loads((row_dir / "result.json").read_text())["status"]
        for row_dir in result_dirs
        if (row_dir / "result.json").is_file()
    ]
    assert "interrupted" in statuses
    assert "crash" not in statuses
    interrupted_result = json.loads(
        next(
            row_dir / "result.json"
            for row_dir in result_dirs
            if json.loads((row_dir / "result.json").read_text())["status"]
            == "interrupted"
        ).read_text()
    )
    assert interrupted_result["public_summary"]["interrupt_class"] == "interrupted"


@pytest.mark.parametrize("cancellation_signal", [signal.SIGINT, signal.SIGTERM])
def test_resume_after_interrupt_runs_remainder_only(
    tmp_path: Path,
    cancellation_signal: signal.Signals,
) -> None:
    pid_dir = tmp_path / "process-tree-pids"
    adapter = _interrupt_adapter(tmp_path, pid_dir=pid_dir, slow_task_id=SLOW_TASK_ID)
    output_dir = tmp_path / "run"
    driver_path = _write_driver(tmp_path, output_dir=output_dir, adapter=adapter)
    driver = subprocess.Popen(
        [sys.executable, str(driver_path)],
        cwd=Path.cwd(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _wait_for_process_tree_start(pid_dir)
        os.kill(driver.pid, cancellation_signal)
        driver.communicate(timeout=SATURATED_HOST_TIMEOUT_SECONDS)
    finally:
        if driver.poll() is None:
            driver.kill()
            driver.wait(timeout=SATURATED_HOST_TIMEOUT_SECONDS)

    script_path = Path(adapter.manifest.command[1])
    script_path.write_text(
        script_path.read_text(encoding="utf-8").replace(
            f"SLOW_TASK_ID = {SLOW_TASK_ID!r}",
            "SLOW_TASK_ID = ''",
        ),
        encoding="utf-8",
    )
    resumed = run_multi_harness(
        _run_config(output_dir=output_dir, adapter=adapter, resume=True)
    )

    assert resumed.interrupted is False
    by_task = {row.task.task_id: row for row in resumed.rows}
    assert by_task[FAST_TASK_ID].resumed is True
    assert by_task[SLOW_TASK_ID].resumed is False
    assert by_task[FAST_TASK_ID].result.status == "succeeded"
    assert by_task[SLOW_TASK_ID].result.status == "succeeded"
    assert (by_task[FAST_TASK_ID].workspace / "run-count.txt").read_text() == "1"
    assert (by_task[SLOW_TASK_ID].workspace / "run-count.txt").read_text() == "1"
    journal = load_progress_journal(output_dir)
    assert journal is not None
    assert journal.status == "completed"
    assert len(journal.completed_row_ids) == 2


def test_corrupt_journal_refuses_resume_legibly(tmp_path: Path) -> None:
    adapter = _fast_adapter(tmp_path)
    output_dir = tmp_path / "run"
    run_multi_harness(_run_config(output_dir=output_dir, adapter=adapter))
    journal_path = output_dir / JOURNAL_FILENAME
    record = json.loads(journal_path.read_text(encoding="utf-8"))
    record["journal_sha256"] = "sha256:" + "f" * 64
    journal_path.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ResumeRefusedError, match="corrupt or unreadable"):
        run_multi_harness(
            _run_config(output_dir=output_dir, adapter=adapter, resume=True)
        )


def test_solver_identity_drift_on_resume_names_the_drift(tmp_path: Path) -> None:
    adapter = _fast_adapter(tmp_path)
    output_dir = tmp_path / "run"
    run_multi_harness(_run_config(output_dir=output_dir, adapter=adapter))
    original_compatibility = (output_dir / "run-compatibility.json").read_text()
    original_manifest = (output_dir / "run-manifest.json").read_text()
    drifted = replace(
        _run_config(output_dir=output_dir, adapter=adapter, resume=True),
        model_configs=(
            ModelConfig(
                adapter_id=adapter.manifest.adapter_id,
                model_key="other-model",
            ),
        ),
    )

    with pytest.raises(ResumeRefusedError, match="solver identity drifted"):
        run_multi_harness(drifted)

    assert (output_dir / "run-compatibility.json").read_text() == original_compatibility
    assert (output_dir / "run-manifest.json").read_text() == original_manifest


def test_resume_without_journal_is_refused(tmp_path: Path) -> None:
    adapter = _fast_adapter(tmp_path)
    output_dir = tmp_path / "run"
    run_multi_harness(_run_config(output_dir=output_dir, adapter=adapter))
    (output_dir / JOURNAL_FILENAME).unlink()

    with pytest.raises(ResumeRefusedError, match="no progress journal"):
        run_multi_harness(
            _run_config(output_dir=output_dir, adapter=adapter, resume=True)
        )


def test_resume_refuses_completed_row_missing_result_artifacts(
    tmp_path: Path,
) -> None:
    adapter = _fast_adapter(tmp_path)
    output_dir = tmp_path / "run"
    run_multi_harness(_run_config(output_dir=output_dir, adapter=adapter))
    result_path = next((output_dir / "rows").glob("*/result.json"))
    result_path.unlink()

    with pytest.raises(ResumeRefusedError, match="missing durable artifacts"):
        run_multi_harness(
            _run_config(output_dir=output_dir, adapter=adapter, resume=True)
        )


def test_resume_refuses_command_timeout_drift(tmp_path: Path) -> None:
    adapter = _fast_adapter(tmp_path)
    output_dir = tmp_path / "run"
    run_multi_harness(_run_config(output_dir=output_dir, adapter=adapter))
    drifted = replace(adapter, timeout_seconds=12)

    with pytest.raises(ResumeRefusedError, match="config identity drifted"):
        run_multi_harness(
            _run_config(output_dir=output_dir, adapter=drifted, resume=True)
        )


def test_in_process_adapter_interrupt_writes_interrupted_receipt(
    tmp_path: Path,
) -> None:
    adapter = _BlockingInProcessAdapter()
    output_dir = tmp_path / "run"

    def _interrupt() -> None:
        time.sleep(0.2)
        os.kill(os.getpid(), signal.SIGINT)

    threading.Thread(target=_interrupt, daemon=True).start()
    run = run_multi_harness(
        MultiHarnessRunConfig(
            task_index=TaskIndex(
                index_id="fixture-index",
                selection_namespace="fixture",
                tasks=(_task(FAST_TASK_ID),),
                index_sha256=SHA256,
            ),
            adapters=(adapter,),
            model_configs=(
                ModelConfig(
                    adapter_id=adapter.manifest.adapter_id,
                    model_key="fixture-model",
                ),
            ),
            sandbox_policy=sandbox_policy(
                policy_id="fixture",
                backend="docker",
                image="python:3.12-slim",
                mounts=(),
                timeout_seconds=30,
            ),
            output_dir=output_dir,
        )
    )

    assert run.interrupted is True
    assert run.rows[0].result.status == "interrupted"


def test_double_resume_after_completion_is_a_noop(tmp_path: Path) -> None:
    adapter = _fast_adapter(tmp_path)
    output_dir = tmp_path / "run"
    first = run_multi_harness(_run_config(output_dir=output_dir, adapter=adapter))
    second = run_multi_harness(
        _run_config(output_dir=output_dir, adapter=adapter, resume=True)
    )
    third = run_multi_harness(
        _run_config(output_dir=output_dir, adapter=adapter, resume=True)
    )

    assert first.rows[0].resumed is False
    assert second.rows[0].resumed is True
    assert third.rows[0].resumed is True
    assert (first.rows[0].workspace / "run-count.txt").read_text() == "1"
    assert (second.rows[0].workspace / "run-count.txt").read_text() == "1"
    assert (third.rows[0].workspace / "run-count.txt").read_text() == "1"


class _BlockingInProcessAdapter:
    def __init__(self) -> None:
        self.manifest = AdapterManifest(
            adapter_id="in-process-fixture",
            display_name="In Process Fixture",
            adapter_version="0.1.0",
            command=("in-process-fixture",),
        )

    def capabilities(self, workspace: Path) -> AdapterCapabilities:
        del workspace
        return AdapterCapabilities(
            adapter_id=self.manifest.adapter_id,
            adapter_version=self.manifest.adapter_version,
            supported_families=("legalforecast_mtd",),
            supported_scoring_modes=("lfb_brier",),
            capabilities_sha256=SHA256,
        )

    def prepare(self, request: RunRequest, workspace: Path) -> AdapterPreparation:
        return AdapterPreparation(
            manifest=self.manifest,
            capabilities=self.capabilities(workspace),
            workspace=workspace,
        )

    def run(self, request: RunRequest, workspace: Path) -> RunResult:
        del request, workspace
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            time.sleep(0.05)
        raise AssertionError("in-process adapter was not interrupted")


def _run_config(
    *,
    output_dir: Path,
    adapter: CommandAdapter,
    resume: bool = False,
) -> MultiHarnessRunConfig:
    tasks = (
        _task(FAST_TASK_ID),
        _task(SLOW_TASK_ID),
    )
    return MultiHarnessRunConfig(
        task_index=TaskIndex(
            index_id="fixture-index",
            selection_namespace="fixture",
            tasks=tasks,
            index_sha256=SHA256,
        ),
        adapters=(adapter,),
        model_configs=(
            ModelConfig(
                adapter_id=adapter.manifest.adapter_id,
                model_key="fixture-model",
            ),
        ),
        sandbox_policy=sandbox_policy(
            policy_id="fixture",
            backend="docker",
            image="python:3.12-slim",
            mounts=(),
            timeout_seconds=30,
        ),
        output_dir=output_dir,
        resume=resume,
    )


def _write_driver(
    tmp_path: Path,
    *,
    output_dir: Path,
    adapter: CommandAdapter,
) -> Path:
    path = tmp_path / "interrupt_driver.py"
    path.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import sys",
                "from pathlib import Path",
                "from legalforecast.multiharness.command_adapter import CommandAdapter",
                "from legalforecast.multiharness.runner import (",
                "    ModelConfig, MultiHarnessRunConfig, run_multi_harness,",
                ")",
                "from legalforecast.multiharness.sandbox import sandbox_policy",
                "from legalforecast.multiharness.spec import (",
                "    AdapterManifest, CanonicalTask, ContributorCredit, TaskIndex,",
                ")",
                "import hashlib, json",
                "SHA256 = 'sha256:' + 'a' * 64",
                f"FAST_TASK_ID = {FAST_TASK_ID!r}",
                f"SLOW_TASK_ID = {SLOW_TASK_ID!r}",
                "def task(task_id):",
                "    payload = {'task_id': task_id}",
                "    digest = hashlib.sha256(",
                "        json.dumps(",
                "            payload, sort_keys=True, separators=(',', ':')",
                "        ).encode()",
                "    ).hexdigest()",
                "    return CanonicalTask(",
                "        task_id=task_id,",
                "        family='legalforecast_mtd',",
                "        scoring_mode='lfb_brier',",
                "        suite_version='fixture-suite',",
                "        source_id=task_id,",
                "        task_sha256=digest,",
                "        metadata={",
                "            'prompt_sha256': hashlib.sha256(",
                "                b'fixture prompt'",
                "            ).hexdigest()",
                "        },",
                "    )",
                f"script = {adapter.manifest.command[1]!r}",
                "adapter = CommandAdapter(",
                "    manifest=AdapterManifest(",
                "        adapter_id='command-fixture',",
                "        display_name='Command Fixture',",
                "        adapter_version='0.1.0',",
                "        command=(sys.executable, script),",
                "        contributors=(",
                "            ContributorCredit(",
                "                role='adapter_author', name='Fixture'",
                "            ),",
                "        ),",
                "    ),",
                "    timeout_seconds=60,",
                "    termination_grace_seconds=0.05,",
                ")",
                "run = run_multi_harness(MultiHarnessRunConfig(",
                "    task_index=TaskIndex(",
                "        index_id='fixture-index',",
                "        selection_namespace='fixture',",
                "        tasks=(task(FAST_TASK_ID), task(SLOW_TASK_ID)),",
                "        index_sha256=SHA256,",
                "    ),",
                "    adapters=(adapter,),",
                "    model_configs=(ModelConfig(",
                "        adapter_id=adapter.manifest.adapter_id,",
                "        model_key='fixture-model',",
                "    ),),",
                "    sandbox_policy=sandbox_policy(",
                "        policy_id='fixture',",
                "        backend='docker',",
                "        image='python:3.12-slim',",
                "        mounts=(),",
                "        timeout_seconds=30,",
                "    ),",
                f"    output_dir=Path({str(output_dir)!r}),",
                "))",
                "print(run.interrupted)",
                "raise SystemExit(130 if run.interrupted else 0)",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _interrupt_adapter(
    tmp_path: Path,
    *,
    pid_dir: Path,
    slow_task_id: str,
) -> CommandAdapter:
    return _write_adapter(
        tmp_path,
        pid_dir=pid_dir,
        slow_task_id=slow_task_id,
    )


def _fast_adapter(tmp_path: Path) -> CommandAdapter:
    return _write_adapter(
        tmp_path,
        pid_dir=tmp_path / "unused-pids",
        slow_task_id="",
    )


def _write_adapter(
    tmp_path: Path,
    *,
    pid_dir: Path,
    slow_task_id: str,
) -> CommandAdapter:
    tree_script, _ = _write_process_tree_script(tmp_path, pid_dir)
    script = tmp_path / "interrupt_adapter.py"
    script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "from __future__ import annotations",
                "import argparse, json, pathlib, subprocess, sys, time",
                f"SLOW_TASK_ID = {slow_task_id!r}",
                f"TREE_SCRIPT = {str(tree_script)!r}",
                f"PID_DIR = pathlib.Path({str(pid_dir)!r})",
                "parser = argparse.ArgumentParser()",
                "sub = parser.add_subparsers(dest='command', required=True)",
                "cap = sub.add_parser('capabilities')",
                "cap.add_argument('--output', required=True)",
                "run = sub.add_parser('run')",
                "run.add_argument('--request', required=True)",
                "run.add_argument('--output', required=True)",
                "run.add_argument('--workspace', required=True)",
                "args = parser.parse_args()",
                "if args.command == 'capabilities':",
                "    pathlib.Path(args.output).write_text(json.dumps({",
                "        'schema_version': (",
                "            'legalforecast.multiharness.adapter_capabilities.v1'",
                "        ),",
                "        'adapter_id': 'command-fixture',",
                "        'adapter_version': '0.1.0',",
                "        'supported_families': ['legalforecast_mtd'],",
                "        'supported_scoring_modes': ['lfb_brier'],",
                "        'supports_sandbox_policy': True,",
                "        'capabilities_sha256': 'sha256:' + 'a' * 64,",
                "    }), encoding='utf-8')",
                "    raise SystemExit(0)",
                "request = json.loads(pathlib.Path(args.request).read_text())",
                "task_id = request['task']['task_id']",
                "if task_id == SLOW_TASK_ID:",
                "    subprocess.Popen([sys.executable, TREE_SCRIPT])",
                "    for _ in range(400):",
                "        ready = all(",
                "            (PID_DIR / name).is_file()",
                "            for name in (",
                "                'parent.pid', 'child.pid', 'grandchild.pid'",
                "            )",
                "        )",
                "        if ready:",
                "            break",
                "        time.sleep(0.01)",
                "    time.sleep(60)",
                "count_path = pathlib.Path(args.workspace) / 'run-count.txt'",
                "try:",
                "    count = int(count_path.read_text(encoding='utf-8')) + 1",
                "except FileNotFoundError:",
                "    count = 1",
                "count_path.write_text(str(count), encoding='utf-8')",
                "pathlib.Path(args.output).write_text(json.dumps({",
                "    'schema_version': 'legalforecast.multiharness.run_result.v1',",
                "    'result_id': request['request_id'] + ':result',",
                "    'request_id': request['request_id'],",
                "    'status': 'succeeded',",
                "    'result_sha256': 'sha256:' + 'b' * 64,",
                "    'artifacts': [],",
                "    'public_summary': {'run_count': count, 'task_id': task_id},",
                "}), encoding='utf-8')",
            ]
        ),
        encoding="utf-8",
    )
    script.chmod(0o755)
    return CommandAdapter(
        manifest=AdapterManifest(
            adapter_id="command-fixture",
            display_name="Command Fixture",
            adapter_version="0.1.0",
            command=(sys.executable, str(script)),
            contributors=(ContributorCredit(role="adapter_author", name="Fixture"),),
        ),
        timeout_seconds=60,
        termination_grace_seconds=0.05,
    )


def _write_process_tree_script(root: Path, pid_dir: Path) -> tuple[Path, Path]:
    pid_dir.mkdir(parents=True, exist_ok=True)
    script = root / "process_tree.py"
    grandchild = (
        "import os, pathlib, signal, time; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        f"pathlib.Path({str(pid_dir / 'grandchild.pid')!r})"
        ".write_text(str(os.getpid()), encoding='utf-8'); "
        "time.sleep(60)"
    )
    child = (
        "import os, pathlib, signal, subprocess, sys, time; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        f"pathlib.Path({str(pid_dir / 'child.pid')!r})"
        ".write_text(str(os.getpid()), encoding='utf-8'); "
        f"subprocess.Popen([sys.executable, '-c', {grandchild!r}]); "
        "time.sleep(60)"
    )
    script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import os, pathlib, signal, subprocess, sys, time",
                f"PID_DIR = pathlib.Path({str(pid_dir)!r})",
                "PID_DIR.mkdir(parents=True, exist_ok=True)",
                "for old_pid in PID_DIR.glob('*.pid'):",
                "    old_pid.unlink()",
                "parent = PID_DIR / 'parent.pid'",
                "parent.write_text(str(os.getpid()), encoding='utf-8')",
                "signal.signal(signal.SIGTERM, signal.SIG_IGN)",
                f"subprocess.Popen([sys.executable, '-c', {child!r}])",
                "for _ in range(400):",
                "    if (PID_DIR / 'child.pid').is_file() and (",
                "        PID_DIR / 'grandchild.pid'",
                "    ).is_file():",
                "        break",
                "    time.sleep(0.01)",
                "time.sleep(60)",
            ]
        ),
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script, pid_dir


def _task(task_id: str) -> CanonicalTask:
    source_packet = {"task_id": task_id}
    task_sha256 = hashlib.sha256(
        json.dumps(source_packet, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return CanonicalTask(
        task_id=task_id,
        family="legalforecast_mtd",
        scoring_mode="lfb_brier",
        suite_version="fixture-suite",
        source_id=task_id,
        task_sha256=task_sha256,
        metadata={"prompt_sha256": hashlib.sha256(b"fixture prompt").hexdigest()},
    )


def _wait_for_process_tree_start(pid_dir: Path) -> None:
    pid_paths = [
        pid_dir / "parent.pid",
        pid_dir / "child.pid",
        pid_dir / "grandchild.pid",
    ]
    deadline = time.monotonic() + SATURATED_HOST_TIMEOUT_SECONDS
    while time.monotonic() < deadline and not all(path.is_file() for path in pid_paths):
        time.sleep(0.01)
    assert all(path.is_file() for path in pid_paths)


def _assert_process_tree_stopped(pid_dir: Path) -> None:
    pid_paths = [
        pid_dir / "parent.pid",
        pid_dir / "child.pid",
        pid_dir / "grandchild.pid",
    ]
    assert all(path.is_file() for path in pid_paths)
    pids = [int(path.read_text(encoding="utf-8")) for path in pid_paths]
    deadline = time.monotonic() + SATURATED_HOST_TIMEOUT_SECONDS
    while time.monotonic() < deadline and any(_pid_is_running(pid) for pid in pids):
        time.sleep(0.01)
    assert not [pid for pid in pids if _pid_is_running(pid)]


def _assert_process_group_stopped(group_id: int) -> None:
    deadline = time.monotonic() + SATURATED_HOST_TIMEOUT_SECONDS
    while time.monotonic() < deadline and _running_group_members(group_id):
        time.sleep(0.01)
    assert not _running_group_members(group_id)


def _running_group_members(group_id: int) -> list[int]:
    members: list[int] = []
    self_pid = os.getpid()
    proc = Path("/proc")
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if pid == self_pid or not _pid_is_running(pid):
            continue
        try:
            if _process_group(pid) == group_id:
                members.append(pid)
        except (FileNotFoundError, ProcessLookupError, ValueError):
            continue
    return members


def _process_group(pid: int) -> int:
    fields = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").split()
    return int(fields[4])


def _pid_is_running(pid: int) -> bool:
    stat_path = Path(f"/proc/{pid}/stat")
    try:
        fields = stat_path.read_text(encoding="utf-8").split()
    except FileNotFoundError:
        return False
    return len(fields) < 3 or fields[2] != "Z"
