from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.cli import main
from pytest import CaptureFixture

JsonRecord = dict[str, Any]


def test_multiharness_appears_in_top_level_help(
    capsys: CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    assert exc_info.value.code == 0
    assert "multiharness" in capsys.readouterr().out


def test_multiharness_tasks_index_and_select_harvey_lab_fixture(
    tmp_path: Path,
) -> None:
    lab_root = _lab_root(tmp_path)
    task_index = tmp_path / "task-index.json"
    selection = tmp_path / "selection.json"

    assert (
        main(
            [
                "multiharness",
                "tasks",
                "index",
                "--suite",
                "harvey-lab",
                "--lab-root",
                str(lab_root),
                "--output",
                str(task_index),
            ]
        )
        == 0
    )

    index_record = _read_json(task_index)
    assert index_record["index_id"] == "harvey-lab"
    assert index_record["tasks"][0]["family"] == "harvey_lab"

    assert (
        main(
            [
                "multiharness",
                "tasks",
                "select",
                "--index",
                str(task_index),
                "--module",
                "corporate",
                "--limit",
                "1",
                "--seed",
                "fixture",
                "--output",
                str(selection),
            ]
        )
        == 0
    )

    selection_record = _read_json(selection)
    assert selection_record["selection_result"]["task_ids"] == [
        "harvey_lab:corporate/merger"
    ]
    assert selection_record["tasks"][0]["metadata"]["module"] == "corporate"


def test_multiharness_adapter_inspect_and_conformance_fixture(
    tmp_path: Path,
) -> None:
    manifest = _fixture_adapter_manifest(tmp_path)
    inspect_dir = tmp_path / "inspect"
    conformance_dir = tmp_path / "conformance"

    assert (
        main(
            [
                "multiharness",
                "adapters",
                "inspect",
                "--adapter-manifest",
                str(manifest),
                "--output-dir",
                str(inspect_dir),
            ]
        )
        == 0
    )

    capabilities = _read_json(inspect_dir / "adapter-capabilities.json")
    assert capabilities["adapter_id"] == "fixture-cli"
    assert "harvey_lab" in capabilities["supported_families"]

    assert (
        main(
            [
                "multiharness",
                "conformance",
                "--adapter-manifest",
                str(manifest),
                "--output-dir",
                str(conformance_dir),
            ]
        )
        == 0
    )

    report = _read_json(conformance_dir / "conformance-report.json")
    assert report["status"] == "passed"
    assert report["checks"]["lfb_fixture_run"].startswith("passed:")


def test_multiharness_run_dry_run_does_not_invoke_adapter(tmp_path: Path) -> None:
    lab_root = _lab_root(tmp_path)
    task_index = tmp_path / "task-index.json"
    manifest = _adapter_manifest(
        tmp_path / "bad-manifest.json",
        command=("definitely-not-a-real-adapter",),
    )
    output_dir = tmp_path / "dry-run"
    assert (
        main(
            [
                "multiharness",
                "tasks",
                "index",
                "--suite",
                "harvey-lab",
                "--lab-root",
                str(lab_root),
                "--output",
                str(task_index),
            ]
        )
        == 0
    )

    assert (
        main(
            [
                "multiharness",
                "run",
                "--task-index",
                str(task_index),
                "--adapter-manifest",
                str(manifest),
                "--model-key",
                "fixture-model",
                "--output-dir",
                str(output_dir),
                "--dry-run",
            ]
        )
        == 0
    )

    plan = _read_json(output_dir / "run-plan.json")
    assert plan["adapter_invocation"] == "skipped"
    assert plan["container_invocation"] == "skipped"
    assert not (output_dir / "adapter-capabilities").exists()


def test_multiharness_run_dry_run_rejects_provider_env_without_egress(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    lab_root = _lab_root(tmp_path)
    task_index = tmp_path / "task-index.json"
    manifest = _adapter_manifest(
        tmp_path / "fixture-manifest.json",
        command=("fixture-adapter",),
    )
    assert (
        main(
            [
                "multiharness",
                "tasks",
                "index",
                "--suite",
                "harvey-lab",
                "--lab-root",
                str(lab_root),
                "--output",
                str(task_index),
            ]
        )
        == 0
    )

    assert (
        main(
            [
                "multiharness",
                "run",
                "--task-index",
                str(task_index),
                "--adapter-manifest",
                str(manifest),
                "--model-key",
                "fixture-model",
                "--output-dir",
                str(tmp_path / "run"),
                "--provider-env-var",
                "OPENAI_API_KEY",
                "--dry-run",
            ]
        )
        == 2
    )
    assert "--allow-provider-egress" in capsys.readouterr().err


def test_multiharness_synthetic_run_and_report(tmp_path: Path) -> None:
    lab_root = _lab_root(tmp_path)
    task_index = tmp_path / "task-index.json"
    manifest = _fixture_adapter_manifest(tmp_path)
    run_dir = tmp_path / "run"
    report_path = tmp_path / "report.json"
    assert (
        main(
            [
                "multiharness",
                "tasks",
                "index",
                "--suite",
                "harvey-lab",
                "--lab-root",
                str(lab_root),
                "--output",
                str(task_index),
            ]
        )
        == 0
    )

    assert (
        main(
            [
                "multiharness",
                "run",
                "--task-index",
                str(task_index),
                "--adapter-manifest",
                str(manifest),
                "--model-key",
                "fixture-model",
                "--output-dir",
                str(run_dir),
                "--run-id",
                "fixture-run",
                "--sandbox-policy-id",
                "fixture-sandbox",
            ]
        )
        == 0
    )

    rows = _read_jsonl(run_dir / "row-results.jsonl")
    assert rows[0]["status"] == "succeeded"
    assert rows[0]["family"] == "harvey_lab"
    assert _read_json(run_dir / "run-manifest.json")["run_id"] == "fixture-run"

    assert (
        main(
            [
                "multiharness",
                "report",
                "--run-dir",
                str(run_dir),
                "--output",
                str(report_path),
            ]
        )
        == 0
    )

    summary = _read_json(report_path)
    assert summary["row_count"] == 1
    assert summary["status_counts"] == {"succeeded": 1}
    assert summary["family_counts"] == {"harvey_lab": 1}


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


def _fixture_adapter_manifest(tmp_path: Path) -> Path:
    script = tmp_path / "fixture_adapter.py"
    script.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import argparse, json, pathlib, sys",
                "ADAPTER_ID = 'fixture-cli'",
                "ADAPTER_VERSION = '0.1.0'",
                "def write_json(path, payload):",
                "    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)",
                "    pathlib.Path(path).write_text(",
                "        json.dumps(payload, sort_keys=True), encoding='utf-8'",
                "    )",
                "def capabilities(argv):",
                "    parser = argparse.ArgumentParser()",
                "    parser.add_argument('--output', required=True)",
                "    args = parser.parse_args(argv)",
                "    write_json(args.output, {",
                "        'schema_version': (",
                "            'legalforecast.multiharness.adapter_capabilities.v1'",
                "        ),",
                "        'adapter_id': ADAPTER_ID,",
                "        'adapter_version': ADAPTER_VERSION,",
                "        'supported_families': ['legalforecast_mtd', 'harvey_lab'],",
                "        'supported_scoring_modes': ['lfb_brier', 'lab_native'],",
                "        'supports_sandbox_policy': True,",
                "        'capabilities_sha256': 'sha256:' + '1' * 64,",
                "    })",
                "def run(argv):",
                "    parser = argparse.ArgumentParser()",
                "    parser.add_argument('--request', required=True)",
                "    parser.add_argument('--output', required=True)",
                "    parser.add_argument('--workspace', required=True)",
                "    args = parser.parse_args(argv)",
                "    request = json.loads(pathlib.Path(args.request).read_text())",
                "    write_json(args.output, {",
                "        'schema_version': 'legalforecast.multiharness.run_result.v1',",
                "        'result_id': request['request_id'] + ':result',",
                "        'request_id': request['request_id'],",
                "        'status': 'succeeded',",
                "        'result_sha256': 'sha256:' + '2' * 64,",
                "        'artifacts': [],",
                "        'public_summary': {",
                "            'task_id': request['task']['task_id'],",
                "            'family': request['task']['family'],",
                (
                    "            'sandbox_policy_id': "
                    "request['sandbox_policy']['policy_id'],"
                ),
                "        },",
                "    })",
                "phase = sys.argv[1]",
                "if phase == 'capabilities':",
                "    capabilities(sys.argv[2:])",
                "elif phase == 'run':",
                "    run(sys.argv[2:])",
                "else:",
                "    raise SystemExit('unsupported phase: ' + phase)",
            ]
        ),
        encoding="utf-8",
    )
    return _adapter_manifest(
        tmp_path / "adapter-manifest.json",
        command=(sys.executable, str(script)),
    )


def _adapter_manifest(path: Path, *, command: tuple[str, ...]) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": "legalforecast.multiharness.adapter_manifest.v1",
                "adapter_id": "fixture-cli",
                "display_name": "Fixture CLI Adapter",
                "adapter_version": "0.1.0",
                "command": list(command),
                "contributors": [],
            }
        ),
        encoding="utf-8",
    )
    return path


def _read_json(path: Path) -> JsonRecord:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(JsonRecord, value)


def _read_jsonl(path: Path) -> list[JsonRecord]:
    records: list[JsonRecord] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = json.loads(line)
        assert isinstance(value, dict)
        records.append(cast(JsonRecord, value))
    return records
