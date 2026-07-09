"""Adapter protocols for multi-harness execution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from legalforecast.multiharness.spec import (
    AdapterCapabilities,
    AdapterManifest,
    RunRequest,
    RunResult,
)


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
