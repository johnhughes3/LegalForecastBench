from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast._json_io import write_json_object
from legalforecast.cli import main
from legalforecast.multiharness.adapter_registry import (
    CLAUDE_CODE_REGISTRY_NAME,
    CODEX_CLI_REGISTRY_NAME,
    HARVEY_LAB_REGISTRY_NAME,
    LFB_NATIVE_REGISTRY_NAME,
)
from legalforecast.multiharness.harvey_lab_projected_tasks import (
    HarveyLabProjectionTaskLoader,
)
from legalforecast.multiharness.harvey_lab_projection import project_harvey_lab_suite
from legalforecast.release.synthetic import issue_synthetic_release
from pytest import CaptureFixture

from test_harvey_lab_projection import FIXTURE_PIN, _issue_196_source

JsonRecord = dict[str, Any]
CLAUDE_MANIFEST = Path("examples/adapters/claude-code/local-cli-adapter-manifest.json")


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


def test_multiharness_tasks_index_accepts_forecast_release_v1(tmp_path: Path) -> None:
    release_root = tmp_path / "release"
    issue_synthetic_release(release_root)
    task_index = tmp_path / "task-index.json"
    solver_root = tmp_path / "solver-inputs"

    assert (
        main(
            [
                "multiharness",
                "tasks",
                "index",
                "--suite",
                "lfb",
                "--forecast-release",
                str(release_root / "forecast-release.json"),
                "--artifact-root",
                str(release_root),
                "--solver-input-root",
                str(solver_root),
                "--output",
                str(task_index),
            ]
        )
        == 0
    )

    record = _read_json(task_index)
    assert len(record["tasks"]) == 3
    assert record["tasks"][0]["metadata"]["release_schema_version"] == (
        "legalforecast.forecast-release.v1"
    )
    assert (solver_root / "solver-input-index.json").is_file()
    assert str(release_root.resolve()) not in json.dumps(record, sort_keys=True)


def test_multiharness_run_refuses_command_adapter_without_release_artifacts(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    release_root = tmp_path / "release"
    issue_synthetic_release(release_root)
    task_index = tmp_path / "task-index.json"
    solver_root = tmp_path / "solver-inputs"
    manifest = _fixture_adapter_manifest(tmp_path)
    assert (
        main(
            [
                "multiharness",
                "tasks",
                "index",
                "--suite",
                "lfb",
                "--forecast-release",
                str(release_root / "forecast-release.json"),
                "--artifact-root",
                str(release_root),
                "--solver-input-root",
                str(solver_root),
                "--output",
                str(task_index),
            ]
        )
        == 0
    )

    output_dir = tmp_path / "run"
    assert (
        main(
            [
                "multiharness",
                "run",
                "--task-index",
                str(task_index),
                "--solver-input-root",
                str(solver_root),
                "--adapter-manifest",
                str(manifest),
                "--model-key",
                "fixture-model",
                "--output-dir",
                str(output_dir),
                "--incomplete-run-policy",
                "fail_fast",
            ]
        )
        == 2
    )
    assert "release adapter result must contain one forecast output artifact" in (
        capsys.readouterr().err
    )
    assert not (output_dir / "release-harness-receipts.jsonl").exists()


def test_multiharness_category_alias_selects_lab_module(tmp_path: Path) -> None:
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
    assert (
        main(
            [
                "multiharness",
                "tasks",
                "select",
                "--index",
                str(task_index),
                "--category",
                "corporate",
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
    assert selection_record["selection_result"]["coverage_kind"] == "scoped"
    assert selection_record["selection_result"]["selection_label"].startswith("scoped:")


def test_multiharness_task_folder_selects_projected_layout(tmp_path: Path) -> None:
    result = project_harvey_lab_suite(
        source_root=_issue_196_source(tmp_path / "lab"),
        solver_root=tmp_path / "projected",
        evaluator_private_root=tmp_path / "private",
        pin=FIXTURE_PIN,
    )
    index = HarveyLabProjectionTaskLoader(
        result.solver_root,
        suite_version="fixture-suite",
    ).load_task_index()
    index_path = tmp_path / "index.json"
    write_json_object(index_path, index.to_record())
    selection = tmp_path / "selection.json"
    assert (
        main(
            [
                "multiharness",
                "tasks",
                "select",
                "--index",
                str(index_path),
                "--task-folder",
                str(result.solver_root),
                "--output",
                str(selection),
            ]
        )
        == 0
    )
    record = _read_json(selection)
    assert record["selection_result"]["task_ids"] == [index.tasks[0].task_id]
    assert record["selection_result"]["coverage_kind"] == "scoped"
    assert str(result.solver_root.resolve()) not in json.dumps(record)


def test_multiharness_task_folder_help_names_the_real_projection_manifest(
    capsys: CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["multiharness", "tasks", "select", "--help"])

    assert exc_info.value.code == 0
    help_text = capsys.readouterr().out
    assert "Harvey LAB root or subfolder" in help_text
    assert "lab-projection.v1.json" in help_text
    assert "projection-manifest.json" not in help_text


def test_multiharness_adapter_inspect_and_conformance_fixture(
    tmp_path: Path,
    capsys: CaptureFixture[str],
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
    captured = capsys.readouterr()
    assert "adapter-capabilities.json" in captured.err
    assert "conformance-report.json" in captured.err


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
                "--host-process-containment",
                "linux_systemd_scope_cgroup_v2.v1",
                "--dry-run",
            ]
        )
        == 0
    )

    plan = _read_json(output_dir / "run-plan.json")
    assert plan["adapter_invocation"] == "skipped"
    assert plan["container_invocation"] == "skipped"
    assert plan["sandbox_policy"]["host_process_containment"] == (
        "linux_systemd_scope_cgroup_v2.v1"
    )
    assert not (output_dir / "adapter-capabilities").exists()


def test_multiharness_run_dry_run_selects_builtin_auth_profile(tmp_path: Path) -> None:
    task_index = _lab_task_index(tmp_path)
    output_dir = tmp_path / "dry-run"
    assert (
        main(
            [
                "multiharness",
                "run",
                "--task-index",
                str(task_index),
                "--adapter-manifest",
                str(CLAUDE_MANIFEST),
                "--auth-profile",
                "published-api-key",
                "--model-key",
                "anthropic:claude-sonnet-4-6",
                "--output-dir",
                str(output_dir),
                "--allow-provider-egress",
                "--dry-run",
            ]
        )
        == 0
    )

    plan = _read_json(output_dir / "run-plan.json")
    assert plan["adapter_auth_profiles"] == {
        "claude-code-clean-native": "published-api-key"
    }
    assert plan["adapter_manifests"][0]["adapter_id"] == ("claude-code-clean-native")


def test_multiharness_run_refuses_unknown_auth_profile_before_plan(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    task_index = _lab_task_index(tmp_path)
    output_dir = tmp_path / "dry-run"
    assert (
        main(
            [
                "multiharness",
                "run",
                "--task-index",
                str(task_index),
                "--adapter-manifest",
                str(CLAUDE_MANIFEST),
                "--auth-profile",
                "not-a-profile",
                "--model-key",
                "anthropic:claude-sonnet-4-6",
                "--output-dir",
                str(output_dir),
                "--dry-run",
            ]
        )
        == 2
    )
    assert "auth_profile 'not-a-profile' is unknown" in capsys.readouterr().err
    assert not (output_dir / "run-plan.json").exists()


def test_multiharness_run_refuses_explicitly_empty_auth_profile(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    task_index = _lab_task_index(tmp_path)
    output_dir = tmp_path / "empty-profile"

    assert (
        main(
            [
                "multiharness",
                "run",
                "--task-index",
                str(task_index),
                "--adapter-manifest",
                str(CLAUDE_MANIFEST),
                "--auth-profile",
                "",
                "--model-key",
                "anthropic:claude-sonnet-4-6",
                "--output-dir",
                str(output_dir),
                "--dry-run",
            ]
        )
        == 2
    )
    assert (
        "auth_profile must be a single canonical profile ID" in capsys.readouterr().err
    )
    assert not output_dir.exists()


@pytest.mark.parametrize(
    ("profile", "extra_args", "message"),
    [
        (
            "published-api-key",
            (),
            "requires the guarded Tier-0 spend-control path",
        ),
        (
            "contributor-subscription",
            ("--dry-run",),
            "has no production local-login presence probe",
        ),
    ],
)
def test_multiharness_run_refuses_unrunnable_auth_profile_before_plan(
    tmp_path: Path,
    capsys: CaptureFixture[str],
    profile: str,
    extra_args: tuple[str, ...],
    message: str,
) -> None:
    task_index = _lab_task_index(tmp_path)
    output_dir = tmp_path / profile

    assert (
        main(
            [
                "multiharness",
                "run",
                "--task-index",
                str(task_index),
                "--adapter-manifest",
                str(CLAUDE_MANIFEST),
                "--auth-profile",
                profile,
                "--model-key",
                "anthropic:claude-sonnet-4-6",
                "--output-dir",
                str(output_dir),
                *extra_args,
            ]
        )
        == 2
    )
    assert message in capsys.readouterr().err
    assert not output_dir.exists()
    assert not (output_dir / "run-plan.json").exists()
    assert not (output_dir / "run-progress.json").exists()


def test_multiharness_live_tool_dry_run_requires_solver_input_store(
    tmp_path: Path,
) -> None:
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
                "--sandbox-image",
                "sha256:" + "a" * 64,
                "--live-tool-container",
                "--dry-run",
            ]
        )
        == 2
    )
    assert not (output_dir / "run-plan.json").exists()
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


def test_cli_lists_builtin_adapters_in_sorted_order(tmp_path: Path) -> None:
    output = tmp_path / "adapters.json"
    assert (
        main(
            [
                "multiharness",
                "adapters",
                "list",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    record = output.read_text(encoding="utf-8")
    assert LFB_NATIVE_REGISTRY_NAME in record
    assert CLAUDE_CODE_REGISTRY_NAME in record
    assert CODEX_CLI_REGISTRY_NAME in record
    assert HARVEY_LAB_REGISTRY_NAME in record
    assert record.index(CLAUDE_CODE_REGISTRY_NAME) < record.index(
        LFB_NATIVE_REGISTRY_NAME
    )


def test_cli_inspect_lfb_native_still_works(tmp_path: Path) -> None:
    output_dir = tmp_path / "inspect"
    assert (
        main(
            [
                "multiharness",
                "adapters",
                "inspect",
                "--adapter",
                LFB_NATIVE_REGISTRY_NAME,
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )
    manifest = (output_dir / "adapter-manifest.json").read_text(encoding="utf-8")
    assert LFB_NATIVE_REGISTRY_NAME in manifest


def test_cli_inspect_refuses_symlinked_capabilities_directory(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "inspect"
    output_dir.mkdir(mode=0o700)
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o700)
    (output_dir / "capabilities").symlink_to(outside, target_is_directory=True)

    assert (
        main(
            [
                "multiharness",
                "adapters",
                "inspect",
                "--adapter",
                LFB_NATIVE_REGISTRY_NAME,
                "--output-dir",
                str(output_dir),
            ]
        )
        == 2
    )
    assert tuple(outside.iterdir()) == ()


def test_cli_unknown_adapter_fails_with_known_names(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    assert (
        main(
            [
                "multiharness",
                "adapters",
                "inspect",
                "--adapter",
                "no-such-adapter",
                "--output-dir",
                str(tmp_path / "inspect"),
            ]
        )
        == 2
    )
    err = capsys.readouterr().err
    assert "unknown adapter" in err
    assert LFB_NATIVE_REGISTRY_NAME in err
    assert CLAUDE_CODE_REGISTRY_NAME in err
    assert CODEX_CLI_REGISTRY_NAME in err


def test_cli_dry_run_inspect_unknown_adapter_fails_before_writing_plan(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    output_dir = tmp_path / "inspect"
    assert (
        main(
            [
                "multiharness",
                "adapters",
                "inspect",
                "--adapter",
                "no-such-adapter",
                "--output-dir",
                str(output_dir),
                "--dry-run",
            ]
        )
        == 2
    )
    err = capsys.readouterr().err
    assert "unknown adapter" in err
    assert LFB_NATIVE_REGISTRY_NAME in err
    assert CLAUDE_CODE_REGISTRY_NAME in err
    assert not (output_dir / "adapter-inspect-plan.json").exists()


def test_cli_dry_run_inspect_known_adapter_writes_plan(tmp_path: Path) -> None:
    output_dir = tmp_path / "inspect"
    assert (
        main(
            [
                "multiharness",
                "adapters",
                "inspect",
                "--adapter",
                LFB_NATIVE_REGISTRY_NAME,
                "--output-dir",
                str(output_dir),
                "--dry-run",
            ]
        )
        == 0
    )
    plan = _read_json(output_dir / "adapter-inspect-plan.json")
    assert plan["dry_run"] is True
    assert plan["adapter_source"]["adapter"] == LFB_NATIVE_REGISTRY_NAME


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


def _lab_task_index(tmp_path: Path) -> Path:
    task_index = tmp_path / "task-index.json"
    assert (
        main(
            [
                "multiharness",
                "tasks",
                "index",
                "--suite",
                "harvey-lab",
                "--lab-root",
                str(_lab_root(tmp_path)),
                "--output",
                str(task_index),
            ]
        )
        == 0
    )
    return task_index


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
