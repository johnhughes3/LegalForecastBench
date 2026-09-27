"""Clean-native adapter admission and selection for the paired Tier-0 runner."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from functools import partial
from typing import cast

from legalforecast.multiharness.adapter_registry import (
    CLAUDE_CODE_REGISTRY_NAME,
    CODEX_CLI_REGISTRY_NAME,
)
from legalforecast.multiharness.adapters import HarnessAdapter
from legalforecast.multiharness.auth_profiles import FIXTURE_NONE
from legalforecast.multiharness.claude_code import (
    CLAUDE_CODE_EXECUTABLE_NAME,
    ClaudeCodeCliAdapter,
)
from legalforecast.multiharness.claude_code_harvey_lab import (
    ClaudeCodeHarveyLabPipelineResult,
    run_claude_code_clean_native_harvey_lab,
)
from legalforecast.multiharness.codex_cli import (
    CODEX_CLI_EXECUTABLE,
    CODEX_DEFAULT_REASONING_EFFORT,
    CODEX_REASONING_EFFORTS,
    CodexCliAdapter,
)
from legalforecast.multiharness.codex_cli_harvey_lab import (
    CodexCliHarveyLabPipelineResult,
    run_codex_cli_clean_native_harvey_lab,
)
from legalforecast.multiharness.local_cli_identity import ExecutableIdentityPin

CLEAN_NATIVE_ADAPTERS = frozenset({CLAUDE_CODE_REGISTRY_NAME, CODEX_CLI_REGISTRY_NAME})


class Tier0RunnerError(ValueError):
    """A frozen Tier-0 run cannot proceed without violating a boundary."""


def validate_clean_native_arm(
    *,
    adapter_name: str,
    executable: str,
    auth_profile: str,
    command: Sequence[str],
    settings: Mapping[str, object],
) -> None:
    """Validate registered clean-native executable and configuration contracts."""

    if command:
        raise Tier0RunnerError("clean-native arm must use its registered adapter")
    if adapter_name == CLAUDE_CODE_REGISTRY_NAME:
        if executable != CLAUDE_CODE_EXECUTABLE_NAME:
            raise Tier0RunnerError(
                "clean-native arm must pin the Claude Code executable"
            )
        return
    if executable != CODEX_CLI_EXECUTABLE:
        raise Tier0RunnerError("clean-native arm must pin the Codex executable")
    if auth_profile != FIXTURE_NONE:
        raise Tier0RunnerError(
            "Codex LAB currently requires fixture-none: paid spend enforcement "
            "and contributor login support are not available"
        )
    effort = settings.get("reasoning_effort", CODEX_DEFAULT_REASONING_EFFORT)
    if not isinstance(effort, str) or effort not in CODEX_REASONING_EFFORTS:
        raise Tier0RunnerError("unsupported Codex reasoning_effort")
    if set(settings) - {"reasoning_effort"}:
        raise Tier0RunnerError("unsupported Codex arm settings")


def require_supported_paid_solvers(adapter_names: Sequence[str]) -> None:
    """Refuse paid solvers without supported mechanical spend enforcement."""

    if CODEX_CLI_REGISTRY_NAME in adapter_names:
        # Codex has no supported monetary CLI flag. A reservation alone cannot
        # bound an agentic invocation; never pretend a token/turn limit can.
        raise Tier0RunnerError("paid Codex LAB has no supported enforced spend control")


def prepare_clean_native_runner(
    adapter: HarnessAdapter,
    *,
    adapter_name: str,
    auth_profile: str,
    settings: Mapping[str, object],
    executable_pin: ExecutableIdentityPin,
    executable_version: str | None,
    max_budget_usd: str | None,
) -> tuple[
    partial[ClaudeCodeHarveyLabPipelineResult]
    | partial[CodexCliHarveyLabPipelineResult],
    dict[str, object],
]:
    """Bind the composition and its capability record for private metadata."""

    expected_type = (
        ClaudeCodeCliAdapter
        if adapter_name == CLAUDE_CODE_REGISTRY_NAME
        else CodexCliAdapter
    )
    if adapter_name not in CLEAN_NATIVE_ADAPTERS or not isinstance(
        adapter, expected_type
    ):
        raise Tier0RunnerError("registry returned the wrong clean-native adapter")
    adapter = replace(adapter, auth_profile=auth_profile)
    manifest = (
        adapter.local_manifest
        if isinstance(adapter, ClaudeCodeCliAdapter)
        else adapter.local_cli_manifest
    )
    capability: dict[str, object] = {
        "manifest": manifest.to_record(),
        "executable": {
            "name": executable_pin.basename,
            "sha256": "sha256:" + executable_pin.sha256,
            "version": executable_version,
        },
    }
    if isinstance(adapter, ClaudeCodeCliAdapter):
        return (
            partial(
                run_claude_code_clean_native_harvey_lab,
                adapter=adapter,
                max_budget_usd=max_budget_usd,
            ),
            capability,
        )
    return (
        partial(
            run_codex_cli_clean_native_harvey_lab,
            adapter=adapter,
            solver_executable_pin=executable_pin,
            reasoning_effort=cast(
                str, settings.get("reasoning_effort", CODEX_DEFAULT_REASONING_EFFORT)
            ),
        ),
        capability,
    )
