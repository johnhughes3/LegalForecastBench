"""Merged release runtimes keep distinct protected descriptor identities."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from legalforecast.multiharness import hermes_paid
from legalforecast.multiharness.claude_code_container import (
    ClaudeCodeContainerAdapterError,
)
from legalforecast.multiharness.openclaw import GATEWAY_HARNESS_ID, OpenClawError
from legalforecast.multiharness.terminal_release import build_terminal_release_adapter

from test_multiharness_openclaw_paid import _issued_options
from test_paid_gateway_descriptor import _ENVIRONMENT


@pytest.mark.parametrize("identity", [GATEWAY_HARNESS_ID, "claude-code-terminal"])
def test_hermes_refuses_another_runtime_descriptor_before_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, identity: str
) -> None:
    for name, value in _ENVIRONMENT.items():
        monkeypatch.setenv(name, value)
    options, _ = _issued_options(tmp_path, harness_id=identity)

    def unexpected_checkout(_: Path) -> None:
        pytest.fail("cross-harness descriptor reached checkout admission")

    monkeypatch.setattr(hermes_paid, "validate_checkout", unexpected_checkout)
    with pytest.raises(ValueError, match="harness"):
        build_terminal_release_adapter(
            replace(options, harness="hermes-agent", hermes_checkout=tmp_path),
            case_count=1,
        )


def test_hermes_issued_identity_is_distinct_and_selects_only_hermes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name, value in _ENVIRONMENT.items():
        monkeypatch.setenv(name, value)
    options, descriptor = _issued_options(tmp_path, harness_id="hermes-agent")
    monkeypatch.setattr(hermes_paid, "validate_checkout", lambda _: tmp_path)
    selected = build_terminal_release_adapter(
        replace(options, harness="hermes-agent", hermes_checkout=tmp_path),
        case_count=1,
    )
    assert isinstance(selected, hermes_paid.ProtectedHermesAdapter)
    assert selected.config.harness_id == descriptor.harness_id == "hermes-agent"
    assert descriptor.max_requests == 8
    for harness in ("openclaw", "claude-code", "claude-code-terminal"):
        error_type = (
            OpenClawError if harness == "openclaw" else ClaudeCodeContainerAdapterError
        )
        with pytest.raises(error_type, match="harness"):
            build_terminal_release_adapter(
                replace(options, harness=harness, image="sha256:" + "1" * 64),
                case_count=1,
            )
