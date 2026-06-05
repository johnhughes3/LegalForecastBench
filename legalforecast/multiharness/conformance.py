"""Adapter conformance suite for multi-harness contributors."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from legalforecast._json_io import read_json_object, write_json_object
from legalforecast.multiharness.command_adapter import (
    CommandAdapter,
    CommandAdapterError,
)
from legalforecast.multiharness.spec import (
    AdapterCapabilities,
    AdapterManifest,
    ArtifactRecord,
    CanonicalTask,
    ConformanceReport,
    RunRequest,
    RunResult,
    SandboxPolicy,
)
from legalforecast.multiharness.validation import validate_public_record

_PASS = "passed"
_FAIL = "failed"
_SKIP = "skipped"
_WARNING = "warning"
_LFB_FIXTURE_REQUEST_ID = "conformance:lfb-fixture"
_LAB_FIXTURE_REQUEST_ID = "conformance:lab-fixture"


@dataclass(frozen=True, slots=True)
class ConformanceRun:
    """Result of one adapter conformance run."""

    report: ConformanceReport
    output_dir: Path


def run_adapter_conformance(
    *,
    adapter_manifest_path: Path,
    output_dir: Path,
    resume: bool = False,
    timeout_seconds: float = 300,
) -> ConformanceRun:
    """Run the default no-provider conformance suite for one adapter manifest."""

    suite = _ConformanceSuite(
        adapter_manifest_path=adapter_manifest_path,
        output_dir=output_dir,
        resume=resume,
        timeout_seconds=timeout_seconds,
    )
    return suite.run()


@dataclass(slots=True)
class _ConformanceSuite:
    adapter_manifest_path: Path
    output_dir: Path
    resume: bool
    timeout_seconds: float

    def run(self) -> ConformanceRun:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        checks: dict[str, str] = {}
        artifacts: list[ArtifactRecord] = []
        manifest: AdapterManifest | None = None
        capabilities: AdapterCapabilities | None = None

        try:
            adapter = CommandAdapter.from_manifest_file(
                self.adapter_manifest_path,
                timeout_seconds=self.timeout_seconds,
            )
            manifest = adapter.manifest
            checks["manifest_validation"] = _passed(
                f"manifest {manifest.adapter_id}@{manifest.adapter_version} is valid"
            )
        except Exception as exc:
            checks["manifest_validation"] = _failed(_plain_error(exc))
            return self._write_report(
                checks=checks,
                artifacts=artifacts,
                manifest=manifest,
            )

        try:
            capabilities = adapter.capabilities(self.output_dir / "capabilities")
            if not capabilities.supports_sandbox_policy:
                raise ValueError("adapter capabilities must support sandbox_policy")
            write_json_object(
                self.output_dir / "adapter-capabilities.json",
                capabilities.to_record(),
            )
            artifacts.append(
                _artifact_for(
                    self.output_dir,
                    self.output_dir / "adapter-capabilities.json",
                    artifact_id="adapter-capabilities",
                )
            )
            checks["capabilities_validation"] = _passed(
                "adapter capabilities match the manifest"
            )
        except Exception as exc:
            checks["capabilities_validation"] = _failed(_plain_error(exc))
            return self._write_report(
                checks=checks,
                artifacts=artifacts,
                manifest=manifest,
            )

        sandbox_path = self.output_dir / "sandbox-negative-control.json"
        write_json_object(
            sandbox_path,
            {
                "purpose": "sandbox-policy negative control",
                "network_policy": "provider_egress_host_only",
                "allowed_provider_env_vars": [],
                "expectation": (
                    "adapter must not require provider credentials for default "
                    "conformance fixtures"
                ),
            },
        )
        artifacts.append(
            _artifact_for(
                self.output_dir,
                sandbox_path,
                artifact_id="sandbox-negative-control",
            )
        )
        checks["sandbox_negative_control"] = _passed(
            "recorded no-provider sandbox negative control"
        )

        lfb_request = _fixture_request(
            manifest=manifest,
            family="legalforecast_mtd",
            scoring_mode="lfb_brier",
            request_id=_LFB_FIXTURE_REQUEST_ID,
        )
        if "legalforecast_mtd" not in capabilities.supported_families:
            checks["lfb_fixture_run"] = _failed(
                "adapter capabilities must include legalforecast_mtd"
            )
        elif "lfb_brier" not in capabilities.supported_scoring_modes:
            checks["lfb_fixture_run"] = _failed(
                "adapter capabilities must include lfb_brier"
            )
        else:
            result = self._run_fixture(
                adapter=adapter,
                request=lfb_request,
                fixture_name="lfb-fixture",
                checks=checks,
                check_prefix="lfb",
            )
            if result is not None:
                artifacts.append(
                    _artifact_for(
                        self.output_dir,
                        self.output_dir / "lfb-fixture" / "result.json",
                        artifact_id="lfb-fixture-result",
                    )
                )

        if "harvey_lab" in capabilities.supported_families:
            lab_request = _fixture_request(
                manifest=manifest,
                family="harvey_lab",
                scoring_mode="lab_native",
                request_id=_LAB_FIXTURE_REQUEST_ID,
            )
            if "lab_native" not in capabilities.supported_scoring_modes:
                checks["lab_fixture_run"] = _failed(
                    "adapter declares harvey_lab but not lab_native scoring"
                )
            else:
                result = self._run_fixture(
                    adapter=adapter,
                    request=lab_request,
                    fixture_name="lab-fixture",
                    checks=checks,
                    check_prefix="lab",
                )
                if result is not None:
                    artifacts.append(
                        _artifact_for(
                            self.output_dir,
                            self.output_dir / "lab-fixture" / "result.json",
                            artifact_id="lab-fixture-result",
                        )
                    )
        else:
            checks["lab_fixture_run"] = _skipped(
                "adapter does not declare harvey_lab support"
            )

        return self._write_report(
            checks=checks,
            artifacts=artifacts,
            manifest=manifest,
        )

    def _run_fixture(
        self,
        *,
        adapter: CommandAdapter,
        request: RunRequest,
        fixture_name: str,
        checks: dict[str, str],
        check_prefix: str,
    ) -> RunResult | None:
        workspace = self.output_dir / fixture_name
        try:
            result = self._run_or_resume_fixture(adapter, request, workspace)
        except Exception as exc:
            checks[f"{check_prefix}_fixture_run"] = _failed(_plain_error(exc))
            return None
        checks[f"{check_prefix}_fixture_run"] = _passed(
            f"{request.task.family} fixture returned a valid result"
        )
        try:
            self._check_sandbox_receipt(result, request)
            checks[f"{check_prefix}_sandbox_policy_receipt"] = _passed(
                "result public_summary echoed sandbox_policy_id"
            )
        except Exception as exc:
            checks[f"{check_prefix}_sandbox_policy_receipt"] = _failed(
                _plain_error(exc)
            )
        try:
            validate_public_record(result.to_record(), "run_result")
            checks[f"{check_prefix}_public_safety_scan"] = _passed(
                "result record passed public-safety validation"
            )
        except Exception as exc:
            checks[f"{check_prefix}_public_safety_scan"] = _failed(_plain_error(exc))
        return result

    def _run_or_resume_fixture(
        self,
        adapter: CommandAdapter,
        request: RunRequest,
        workspace: Path,
    ) -> RunResult:
        request_path = workspace / "request.json"
        result_path = workspace / "result.json"
        if self.resume and request_path.is_file() and result_path.is_file():
            existing_request = RunRequest.from_record(
                _read_json(request_path, "fixture request")
            )
            if existing_request.request_sha256 == request.request_sha256:
                result = RunResult.from_record(
                    _read_json(result_path, "fixture result")
                )
                if result.request_id == request.request_id:
                    return result
        return adapter.run(request, workspace)

    def _check_sandbox_receipt(
        self,
        result: RunResult,
        request: RunRequest,
    ) -> None:
        actual = result.public_summary.get("sandbox_policy_id")
        if actual != request.sandbox_policy.policy_id:
            raise ValueError(
                "result public_summary must echo sandbox_policy_id="
                f"{request.sandbox_policy.policy_id}"
            )

    def _write_report(
        self,
        *,
        checks: Mapping[str, str],
        artifacts: list[ArtifactRecord],
        manifest: AdapterManifest | None,
    ) -> ConformanceRun:
        adapter_id = manifest.adapter_id if manifest is not None else "unknown"
        adapter_version = (
            manifest.adapter_version if manifest is not None else "unknown"
        )
        status = _status_for_checks(checks)
        markdown_path = self.output_dir / "conformance-report.md"
        markdown_path.write_text(
            _markdown_report(
                adapter_id=adapter_id,
                adapter_version=adapter_version,
                status=status,
                checks=checks,
            ),
            encoding="utf-8",
        )
        report_artifacts = [
            *artifacts,
            _artifact_for(
                self.output_dir,
                markdown_path,
                artifact_id="conformance-report-md",
                media_type="text/markdown",
            ),
        ]
        report = ConformanceReport(
            report_id=f"conformance:{adapter_id}:{adapter_version}",
            adapter_id=adapter_id,
            adapter_version=adapter_version,
            status=status,
            checks=dict(sorted(checks.items())),
            artifacts=tuple(report_artifacts),
        )
        write_json_object(
            self.output_dir / "conformance-report.json",
            report.to_record(),
        )
        return ConformanceRun(report=report, output_dir=self.output_dir)


def _fixture_request(
    *,
    manifest: AdapterManifest,
    family: str,
    scoring_mode: str,
    request_id: str,
) -> RunRequest:
    task = CanonicalTask(
        task_id=f"{family}:conformance-fixture",
        family=family,
        scoring_mode=scoring_mode,
        suite_version="conformance-fixture",
        source_id="conformance-fixture",
        task_sha256=_record_sha256(
            {
                "family": family,
                "scoring_mode": scoring_mode,
                "source_id": "conformance-fixture",
            },
            prefixed=True,
        ),
        metadata={
            "fixture": "adapter-conformance",
            "family": family,
            "scoring_mode": scoring_mode,
        },
    )
    sandbox = _sandbox_policy(request_id)
    payload = {
        "request_id": request_id,
        "task": task.to_record(),
        "adapter": manifest.to_record(),
        "model_key": "conformance-fixture-model",
        "sandbox_policy": sandbox.to_record(),
    }
    return RunRequest(
        request_id=request_id,
        task=task,
        adapter=manifest,
        model_key="conformance-fixture-model",
        sandbox_policy=sandbox,
        request_sha256=_record_sha256(payload, prefixed=True),
    )


def _sandbox_policy(request_id: str) -> SandboxPolicy:
    return SandboxPolicy(
        policy_id=f"{request_id}:sandbox",
        backend="docker",
        image="python:3.12-slim",
        network_policy="provider_egress_host_only",
        timeout_seconds=30,
        working_directory="/workspace",
        allowed_provider_env_vars=(),
    )


def _artifact_for(
    root: Path,
    path: Path,
    *,
    artifact_id: str,
    media_type: str = "application/json",
) -> ArtifactRecord:
    return ArtifactRecord(
        artifact_id=artifact_id,
        path=path.relative_to(root).as_posix(),
        sha256=_file_sha256(path),
        media_type=media_type,
        public=True,
        size_bytes=path.stat().st_size,
    )


def _read_json(path: Path, label: str) -> Mapping[str, Any]:
    return read_json_object(
        path,
        error_factory=CommandAdapterError,
        missing_message=lambda item: f"{label} does not exist: {item}",
        non_object_message=lambda item: f"{label} must be a JSON object: {item}",
    )


def _markdown_report(
    *,
    adapter_id: str,
    adapter_version: str,
    status: str,
    checks: Mapping[str, str],
) -> str:
    lines = [
        "# Adapter Conformance Report",
        "",
        f"Adapter: `{adapter_id}`",
        f"Version: `{adapter_version}`",
        f"Status: `{status}`",
        "",
        "## Checks",
        "",
    ]
    for name, value in sorted(checks.items()):
        lines.append(f"- `{name}`: {value}")
    return "\n".join(lines) + "\n"


def _status_for_checks(checks: Mapping[str, str]) -> str:
    if any(value.startswith(f"{_FAIL}:") for value in checks.values()):
        return "failed"
    if any(value.startswith(f"{_WARNING}:") for value in checks.values()):
        return "warning"
    return "passed"


def _plain_error(exc: Exception) -> str:
    text = str(exc).strip()
    if not text:
        text = exc.__class__.__name__
    return text


def _passed(message: str) -> str:
    return f"{_PASS}: {message}"


def _failed(message: str) -> str:
    return f"{_FAIL}: {message}"


def _skipped(message: str) -> str:
    return f"{_SKIP}: {message}"


def _file_sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _record_sha256(record: Mapping[str, Any], *, prefixed: bool) -> str:
    encoded = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    if prefixed:
        return f"sha256:{digest}"
    return digest
