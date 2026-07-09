"""Built-in fixture-only adapter for LegalForecastBench tasks."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from legalforecast.evals.inspect_task import (
    DEFAULT_TOOL_CALL_CAP,
    HarnessSolver,
    InspectTaskRun,
    build_inspect_samples,
    run_inspect_fixture,
)
from legalforecast.evals.packet_builder import ModelPacket
from legalforecast.multiharness.adapters import AdapterError, AdapterPreparation
from legalforecast.multiharness.artifacts import (
    AdapterRunResult,
    project_lfb_adapter_record,
)
from legalforecast.multiharness.spec import (
    AdapterCapabilities,
    AdapterManifest,
    RunRequest,
    RunResult,
)

LFB_NATIVE_ADAPTER_ID = "lfb-native"
LFB_NATIVE_ADAPTER_VERSION = "0.1.0"


class LfbNativeAdapterError(AdapterError):
    """Raised when the fixture-only native adapter is misused."""


def lfb_native_manifest() -> AdapterManifest:
    """Return the built-in adapter manifest for LFB native fixture runs."""

    return AdapterManifest(
        adapter_id=LFB_NATIVE_ADAPTER_ID,
        display_name="LegalForecastBench Native Fixture Adapter",
        adapter_version=LFB_NATIVE_ADAPTER_VERSION,
        command=("legalforecast.multiharness.lfb_native:LfbNativeAdapter",),
    )


@dataclass(frozen=True, slots=True)
class LfbNativeFixtureRun:
    """Complete native fixture run with private inspect and public result rows."""

    inspect_run: InspectTaskRun
    projected_results: tuple[AdapterRunResult, ...]

    @property
    def inspect_records(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(result.inspect_record for result in self.projected_results)

    @property
    def results(self) -> tuple[RunResult, ...]:
        return tuple(result.result for result in self.projected_results)


@dataclass(frozen=True, slots=True)
class LfbNativeAdapter:
    """Run LFB packets through the repo's local no-network fixture harness."""

    manifest: AdapterManifest = field(default_factory=lfb_native_manifest)

    def capabilities(self, workspace: Path) -> AdapterCapabilities:
        workspace.mkdir(parents=True, exist_ok=True)
        return lfb_native_capabilities(self.manifest)

    def prepare(self, request: RunRequest, workspace: Path) -> AdapterPreparation:
        workspace.mkdir(parents=True, exist_ok=True)
        capabilities = self.capabilities(workspace)
        if request.adapter.adapter_id != self.manifest.adapter_id:
            raise LfbNativeAdapterError(
                "run request adapter ID does not match manifest"
            )
        if request.adapter.adapter_version != self.manifest.adapter_version:
            raise LfbNativeAdapterError(
                "run request adapter version does not match manifest"
            )
        if request.task.family not in capabilities.supported_families:
            raise LfbNativeAdapterError(
                f"adapter does not support task family: {request.task.family}"
            )
        if request.task.scoring_mode not in capabilities.supported_scoring_modes:
            raise LfbNativeAdapterError(
                f"adapter does not support scoring mode: {request.task.scoring_mode}"
            )
        return AdapterPreparation(
            manifest=self.manifest,
            capabilities=capabilities,
            workspace=workspace,
        )

    def run(self, request: RunRequest, workspace: Path) -> RunResult:
        self.prepare(request, workspace)
        raise LfbNativeAdapterError(
            "LfbNativeAdapter is fixture-only; use run_fixture_packet() with a "
            "frozen ModelPacket and offline HarnessSolver"
        )

    def run_fixture_packet(
        self,
        *,
        request: RunRequest,
        packet: ModelPacket,
        solver: HarnessSolver,
        workspace: Path,
        max_tool_calls: int = DEFAULT_TOOL_CALL_CAP,
        run_label: str | None = None,
        use_docket_tool: bool = True,
        latency_ms: float | int | None = None,
    ) -> LfbNativeFixtureRun:
        """Run one frozen packet/solver pair through the LFB fixture harness."""

        self.prepare(request, workspace)
        _validate_packet_matches_task(request, packet)
        samples = build_inspect_samples(
            (packet,),
            max_tool_calls=max_tool_calls,
            run_label=run_label,
            use_docket_tool=use_docket_tool,
        )
        inspect_run = run_inspect_fixture(samples, (solver,))
        projected_results = tuple(
            project_lfb_adapter_record(
                record,
                request,
                latency_ms=latency_ms,
            )
            for record in inspect_run.to_records()
        )
        return LfbNativeFixtureRun(
            inspect_run=inspect_run,
            projected_results=projected_results,
        )


def lfb_native_capabilities(
    manifest: AdapterManifest | None = None,
) -> AdapterCapabilities:
    """Return the deterministic capabilities record for the built-in adapter."""

    active_manifest = manifest or lfb_native_manifest()
    payload = {
        "adapter_id": active_manifest.adapter_id,
        "adapter_version": active_manifest.adapter_version,
        "supported_families": ["legalforecast_mtd"],
        "supported_scoring_modes": ["lfb_brier"],
        "supports_sandbox_policy": True,
    }
    return AdapterCapabilities(
        adapter_id=active_manifest.adapter_id,
        adapter_version=active_manifest.adapter_version,
        supported_families=("legalforecast_mtd",),
        supported_scoring_modes=("lfb_brier",),
        supports_sandbox_policy=True,
        capabilities_sha256=_record_sha256(payload),
    )


def _validate_packet_matches_task(request: RunRequest, packet: ModelPacket) -> None:
    metadata = request.task.metadata
    _require_metadata_match(metadata, "candidate_id", packet.candidate_id)
    _require_metadata_match(metadata, "case_id", packet.case_id)
    _require_metadata_match(metadata, "ablation", packet.ablation.value)
    expected_units = metadata.get("required_unit_ids")
    actual_units = tuple(
        unit.unit_id for unit in packet.prediction_units if unit.should_score
    )
    if expected_units is not None and list(actual_units) != expected_units:
        raise LfbNativeAdapterError(
            "request task required_unit_ids do not match packet"
        )
    packet_sha256 = _record_sha256(packet.to_record(), prefixed=False)
    if request.task.task_sha256 != packet_sha256:
        raise LfbNativeAdapterError("request task hash does not match packet")


def _require_metadata_match(
    metadata: Mapping[str, Any],
    field_name: str,
    expected: str,
) -> None:
    actual = metadata.get(field_name)
    if actual != expected:
        raise LfbNativeAdapterError(f"request task {field_name} does not match packet")


def _record_sha256(record: Mapping[str, Any], *, prefixed: bool = True) -> str:
    encoded = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    if prefixed:
        return f"sha256:{digest}"
    return digest
