"""Adapter protocols for multi-harness execution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from legalforecast.multiharness.spec import (
    AdapterCapabilities,
    AdapterManifest,
    RunRequest,
    RunResult,
)
from legalforecast.multiharness.tool_protocol import ToolRequest, ToolResponse


class AdapterError(RuntimeError):
    """Base exception for adapter execution failures."""


@dataclass(frozen=True, slots=True)
class AdapterPreparation:
    """Prepared adapter state for one run workspace."""

    manifest: AdapterManifest
    capabilities: AdapterCapabilities
    workspace: Path


class HarnessAdapter(Protocol):
    """Protocol implemented by in-process and command adapters."""

    @property
    def manifest(self) -> AdapterManifest:
        """Public adapter manifest."""
        raise NotImplementedError("adapter manifest is provided by implementations")

    def capabilities(self, workspace: Path) -> AdapterCapabilities:
        """Return adapter capabilities, writing private artifacts under workspace."""
        raise NotImplementedError(
            "adapter capabilities are provided by implementations"
        )

    def prepare(self, request: RunRequest, workspace: Path) -> AdapterPreparation:
        """Validate and prepare a request before execution."""
        raise NotImplementedError("adapter preparation is provided by implementations")

    def run(self, request: RunRequest, workspace: Path) -> RunResult:
        """Run one request and return a validated canonical result."""
        raise NotImplementedError("adapter execution is provided by implementations")


class ToolExecutor(Protocol):
    """Host-owned executor for one validated live tool request."""

    def execute(self, request: ToolRequest, workspace: Path) -> ToolResponse:
        """Execute one tool operation without exposing host provider credentials."""
        raise NotImplementedError("tool execution is provided by implementations")


@runtime_checkable
class LiveToolAdapter(HarnessAdapter, Protocol):
    """Adapter that can exchange live tool calls with a host-owned executor."""

    def run_with_tools(
        self,
        request: RunRequest,
        workspace: Path,
        tool_executor: ToolExecutor,
    ) -> RunResult:
        """Run one request using a bounded host-owned tool RPC channel."""
        raise NotImplementedError("live tool execution is provided by implementations")


@runtime_checkable
class SolverInputAdapter(HarnessAdapter, Protocol):
    """Adapter that consumes a host-authenticated private solver-input tree."""

    def run_with_solver_input(
        self,
        request: RunRequest,
        workspace: Path,
        solver_input_root: Path,
    ) -> RunResult:
        """Run with exact input bytes kept outside serialized task metadata."""

        raise NotImplementedError(
            "solver-input execution is provided by implementations"
        )
