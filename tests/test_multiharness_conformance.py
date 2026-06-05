from __future__ import annotations

import json
import sys
from pathlib import Path

from legalforecast.multiharness.conformance import run_adapter_conformance


def test_conformance_passes_fixture_adapter_and_resumes(tmp_path: Path) -> None:
    manifest_path = _write_manifest(
        tmp_path,
        capabilities=_capabilities(
            supported_families=("legalforecast_mtd", "harvey_lab"),
            supported_scoring_modes=("lfb_brier", "lab_native"),
        ),
    )
    output_dir = tmp_path / "conformance"

    first = run_adapter_conformance(
        adapter_manifest_path=manifest_path,
        output_dir=output_dir,
    )
    second = run_adapter_conformance(
        adapter_manifest_path=manifest_path,
        output_dir=output_dir,
        resume=True,
    )

    assert first.report.status == "passed"
    assert second.report.status == "passed"
    assert (output_dir / "conformance-report.json").is_file()
    assert (
        (output_dir / "conformance-report.md")
        .read_text(encoding="utf-8")
        .startswith("# Adapter Conformance Report")
    )
    assert (output_dir / "adapter-capabilities.json").is_file()
    assert (output_dir / "sandbox-negative-control.json").is_file()
    assert (output_dir / "lfb-fixture" / "result.json").is_file()
    assert (output_dir / "lab-fixture" / "result.json").is_file()
    assert (output_dir / "lfb-fixture" / "run-count.txt").read_text(
        encoding="utf-8"
    ) == "1"
    assert (output_dir / "lab-fixture" / "run-count.txt").read_text(
        encoding="utf-8"
    ) == "1"
    assert first.report.checks["lfb_sandbox_policy_receipt"].startswith("passed:")
    assert first.report.checks["lab_public_safety_scan"].startswith("passed:")
    assert {artifact.artifact_id for artifact in first.report.artifacts} >= {
        "adapter-capabilities",
        "lfb-fixture-result",
        "lab-fixture-result",
        "sandbox-negative-control",
        "conformance-report-md",
    }


def test_conformance_passes_without_lab_when_not_declared(tmp_path: Path) -> None:
    manifest_path = _write_manifest(
        tmp_path,
        capabilities=_capabilities(
            supported_families=("legalforecast_mtd",),
            supported_scoring_modes=("lfb_brier",),
        ),
    )

    run = run_adapter_conformance(
        adapter_manifest_path=manifest_path,
        output_dir=tmp_path / "conformance",
    )

    assert run.report.status == "passed"
    assert run.report.checks["lab_fixture_run"].startswith("skipped:")


def test_conformance_fails_when_sandbox_policy_not_echoed(tmp_path: Path) -> None:
    manifest_path = _write_manifest(
        tmp_path,
        capabilities=_capabilities(
            supported_families=("legalforecast_mtd",),
            supported_scoring_modes=("lfb_brier",),
        ),
        omit_sandbox_echo=True,
    )

    run = run_adapter_conformance(
        adapter_manifest_path=manifest_path,
        output_dir=tmp_path / "conformance",
    )

    assert run.report.status == "failed"
    assert run.report.checks["lfb_sandbox_policy_receipt"].startswith("failed:")
    assert "sandbox_policy_id" in run.report.checks["lfb_sandbox_policy_receipt"]


def test_conformance_fails_on_secret_like_public_summary(tmp_path: Path) -> None:
    manifest_path = _write_manifest(
        tmp_path,
        capabilities=_capabilities(
            supported_families=("legalforecast_mtd",),
            supported_scoring_modes=("lfb_brier",),
        ),
        leak_secret_field=True,
    )

    run = run_adapter_conformance(
        adapter_manifest_path=manifest_path,
        output_dir=tmp_path / "conformance",
    )

    assert run.report.status == "failed"
    assert run.report.checks["lfb_fixture_run"].startswith("failed:")
    assert "secret field" in run.report.checks["lfb_fixture_run"]


def test_conformance_fails_on_capability_manifest_mismatch(tmp_path: Path) -> None:
    manifest_path = _write_manifest(
        tmp_path,
        capabilities={
            **_capabilities(
                supported_families=("legalforecast_mtd",),
                supported_scoring_modes=("lfb_brier",),
            ),
            "adapter_id": "different-adapter",
        },
    )

    run = run_adapter_conformance(
        adapter_manifest_path=manifest_path,
        output_dir=tmp_path / "conformance",
    )

    assert run.report.status == "failed"
    assert run.report.checks["capabilities_validation"].startswith("failed:")
    assert "does not match manifest" in run.report.checks["capabilities_validation"]


def _write_manifest(
    root: Path,
    *,
    capabilities: dict[str, object],
    omit_sandbox_echo: bool = False,
    leak_secret_field: bool = False,
) -> Path:
    script = _write_adapter_script(
        root,
        capabilities=capabilities,
        omit_sandbox_echo=omit_sandbox_echo,
        leak_secret_field=leak_secret_field,
    )
    manifest = {
        "schema_version": "legalforecast.multiharness.adapter_manifest.v1",
        "adapter_id": "fixture-adapter",
        "display_name": "Fixture Adapter",
        "adapter_version": "0.1.0",
        "command": [sys.executable, str(script)],
        "contributors": [{"role": "adapter_author", "name": "Fixture"}],
    }
    path = root / "adapter.json"
    path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    return path


def _write_adapter_script(
    root: Path,
    *,
    capabilities: dict[str, object],
    omit_sandbox_echo: bool,
    leak_secret_field: bool,
) -> Path:
    script = root / "fixture_adapter.py"
    script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "from __future__ import annotations",
                "import argparse, json",
                f"CAPABILITIES = {capabilities!r}",
                f"OMIT_SANDBOX_ECHO = {omit_sandbox_echo!r}",
                f"LEAK_SECRET_FIELD = {leak_secret_field!r}",
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
                "    with open(args.output, 'w', encoding='utf-8') as handle:",
                "        handle.write(json.dumps(CAPABILITIES, sort_keys=True))",
                "else:",
                "    request = json.load(open(args.request, encoding='utf-8'))",
                "    count_path = f'{args.workspace}/run-count.txt'",
                "    try:",
                "        count = int(open(count_path, encoding='utf-8').read()) + 1",
                "    except FileNotFoundError:",
                "        count = 1",
                "    with open(count_path, 'w', encoding='utf-8') as handle:",
                "        handle.write(str(count))",
                "    public_summary = {",
                "        'family': request['task']['family'],",
                "        'model_key': request['model_key'],",
                "        'run_count': count,",
                "    }",
                "    if not OMIT_SANDBOX_ECHO:",
                "        public_summary['sandbox_policy_id'] = (",
                "            request['sandbox_policy']['policy_id']",
                "        )",
                "    if LEAK_SECRET_FIELD:",
                "        public_summary['api_key'] = 'sk-test-secret-value'",
                "    result = {",
                "        'schema_version': 'legalforecast.multiharness.run_result.v1',",
                "        'result_id': request['request_id'] + ':result',",
                "        'request_id': request['request_id'],",
                "        'status': 'succeeded',",
                "        'result_sha256': 'sha256:' + 'b' * 64,",
                "        'artifacts': [],",
                "        'public_summary': public_summary,",
                "    }",
                "    with open(args.output, 'w', encoding='utf-8') as handle:",
                "        handle.write(json.dumps(result, sort_keys=True))",
            ]
        ),
        encoding="utf-8",
    )
    return script


def _capabilities(
    *,
    supported_families: tuple[str, ...],
    supported_scoring_modes: tuple[str, ...],
) -> dict[str, object]:
    return {
        "schema_version": "legalforecast.multiharness.adapter_capabilities.v1",
        "adapter_id": "fixture-adapter",
        "adapter_version": "0.1.0",
        "supported_families": list(supported_families),
        "supported_scoring_modes": list(supported_scoring_modes),
        "supports_sandbox_policy": True,
        "capabilities_sha256": "sha256:" + "a" * 64,
    }
