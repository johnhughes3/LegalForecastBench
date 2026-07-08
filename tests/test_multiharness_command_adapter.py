from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from legalforecast.multiharness.command_adapter import (
    CommandAdapter,
    CommandAdapterError,
)
from legalforecast.multiharness.spec import (
    AdapterManifest,
    CanonicalTask,
    ContributorCredit,
    RunRequest,
    SandboxPolicy,
)

SHA256 = "sha256:" + "a" * 64
OTHER_SHA256 = "sha256:" + "b" * 64


def test_manifest_file_validation_and_capabilities_loading(tmp_path: Path) -> None:
    script = _write_adapter_script(tmp_path)
    manifest_path = _write_manifest(tmp_path, command=(sys.executable, str(script)))

    adapter = CommandAdapter.from_manifest_file(manifest_path)
    capabilities = adapter.capabilities(tmp_path / "workspace")

    assert capabilities.adapter_id == "fixture-adapter"
    assert capabilities.supported_families == ("legalforecast_mtd",)


def test_relative_command_resolution(tmp_path: Path) -> None:
    script = _write_adapter_script(tmp_path / "bin")
    script.chmod(0o755)
    manifest_path = _write_manifest(tmp_path, command=("bin/fixture_adapter.py",))

    adapter = CommandAdapter.from_manifest_file(manifest_path)
    capabilities = adapter.capabilities(tmp_path / "workspace")

    assert capabilities.adapter_version == "0.1.0"


def test_command_adapter_run_invocation_and_private_log_handling(
    tmp_path: Path,
) -> None:
    script = _write_adapter_script(tmp_path)
    manifest = _manifest(command=(sys.executable, str(script)))
    adapter = CommandAdapter(manifest=manifest)
    workspace = tmp_path / "workspace"

    result = adapter.run(_run_request(manifest), workspace)

    assert result.status == "succeeded"
    assert result.public_summary == {"summary": "ok"}
    assert "SECRET_STDOUT" not in json.dumps(result.to_record(), sort_keys=True)
    assert (workspace / "private-logs" / "run-stdout.log").read_text(
        encoding="utf-8"
    ).strip() == "SECRET_STDOUT"
    assert (workspace / "request.json").is_file()
    assert (workspace / "result.json").is_file()


def test_command_adapter_timeout_is_enforced(tmp_path: Path) -> None:
    script = _write_adapter_script(tmp_path, sleep_seconds=1)
    adapter = CommandAdapter(
        manifest=_manifest(command=(sys.executable, str(script))),
        timeout_seconds=0.01,
    )

    with pytest.raises(CommandAdapterError, match="timed out"):
        adapter.capabilities(tmp_path / "workspace")


def test_command_adapter_rejects_unsafe_result_artifacts(tmp_path: Path) -> None:
    script = _write_adapter_script(tmp_path, unsafe_artifact=True)
    adapter = CommandAdapter(manifest=_manifest(command=(sys.executable, str(script))))

    with pytest.raises(ValueError, match="parent"):
        adapter.run(_run_request(adapter.manifest), tmp_path / "workspace")


def test_command_adapter_reports_nonzero_exit_without_public_logs(
    tmp_path: Path,
) -> None:
    script = _write_adapter_script(tmp_path, fail=True)
    adapter = CommandAdapter(manifest=_manifest(command=(sys.executable, str(script))))
    workspace = tmp_path / "workspace"

    with pytest.raises(CommandAdapterError, match="see private logs"):
        adapter.capabilities(workspace)

    assert (workspace / "private-logs" / "capabilities-stderr.log").read_text(
        encoding="utf-8"
    ).strip() == "SECRET_STDERR"


def _write_adapter_script(
    root: Path,
    *,
    sleep_seconds: float = 0,
    unsafe_artifact: bool = False,
    fail: bool = False,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    script = root / "fixture_adapter.py"
    script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "from __future__ import annotations",
                "import argparse, json, sys, time",
                f"SLEEP_SECONDS = {sleep_seconds!r}",
                f"UNSAFE_ARTIFACT = {unsafe_artifact!r}",
                f"FAIL = {fail!r}",
                f"SHA256 = {SHA256!r}",
                f"OTHER_SHA256 = {OTHER_SHA256!r}",
                "CAP_SCHEMA = 'legalforecast.multiharness.adapter_capabilities.v1'",
                "RESULT_SCHEMA = 'legalforecast.multiharness.run_result.v1'",
                "if SLEEP_SECONDS:",
                "    time.sleep(SLEEP_SECONDS)",
                "parser = argparse.ArgumentParser()",
                "sub = parser.add_subparsers(dest='command', required=True)",
                "cap = sub.add_parser('capabilities')",
                "cap.add_argument('--output', required=True)",
                "run = sub.add_parser('run')",
                "run.add_argument('--request', required=True)",
                "run.add_argument('--output', required=True)",
                "run.add_argument('--workspace', required=True)",
                "args = parser.parse_args()",
                "if FAIL:",
                "    print('SECRET_STDERR', file=sys.stderr)",
                "    raise SystemExit(2)",
                "if args.command == 'capabilities':",
                "    payload = {",
                "      'schema_version': CAP_SCHEMA,",
                "      'adapter_id': 'fixture-adapter',",
                "      'adapter_version': '0.1.0',",
                "      'supported_families': ['legalforecast_mtd'],",
                "      'supported_scoring_modes': ['lfb_brier'],",
                "      'supports_sandbox_policy': True,",
                "      'capabilities_sha256': SHA256,",
                "    }",
                "    with open(args.output, 'w', encoding='utf-8') as handle:",
                "        handle.write(json.dumps(payload))",
                "else:",
                "    request = json.load(open(args.request, encoding='utf-8'))",
                "    if UNSAFE_ARTIFACT:",
                "        artifact_path = '../private.txt'",
                "    else:",
                "        artifact_path = 'artifacts/output.json'",
                "    payload = {",
                "      'schema_version': RESULT_SCHEMA,",
                "      'result_id': 'result-1',",
                "      'request_id': request['request_id'],",
                "      'status': 'succeeded',",
                "      'result_sha256': OTHER_SHA256,",
                "      'artifacts': [",
                "        {",
                "          'artifact_id': 'output',",
                "          'path': artifact_path,",
                "          'sha256': SHA256,",
                "          'media_type': 'application/json',",
                "          'public': False,",
                "        }",
                "      ],",
                "      'public_summary': {'summary': 'ok'},",
                "    }",
                "    print('SECRET_STDOUT')",
                "    with open(args.output, 'w', encoding='utf-8') as handle:",
                "        handle.write(json.dumps(payload))",
            ]
        ),
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def _write_manifest(tmp_path: Path, *, command: tuple[str, ...]) -> Path:
    path = tmp_path / "adapter.json"
    path.write_text(
        json.dumps(_manifest(command=command).to_record()),
        encoding="utf-8",
    )
    return path


def _manifest(*, command: tuple[str, ...]) -> AdapterManifest:
    return AdapterManifest(
        adapter_id="fixture-adapter",
        display_name="Fixture Adapter",
        adapter_version="0.1.0",
        command=command,
        contributors=(ContributorCredit(role="adapter_author", name="Fixture"),),
    )


def _run_request(manifest: AdapterManifest) -> RunRequest:
    return RunRequest(
        request_id="request-1",
        task=CanonicalTask(
            task_id="lfb:case-1:full_packet",
            family="legalforecast_mtd",
            scoring_mode="lfb_brier",
            suite_version="fixture",
            source_id="case-1",
            task_sha256=SHA256,
            metadata={"case_id": "case-1"},
        ),
        adapter=manifest,
        model_key="fixture/model",
        sandbox_policy=SandboxPolicy(
            policy_id="fixture",
            backend="docker",
            image="python:3.12-slim",
            network_policy="provider_egress_host_only",
            timeout_seconds=30,
            working_directory="/workspace",
        ),
        request_sha256=OTHER_SHA256,
    )
