from __future__ import annotations

import subprocess
from collections.abc import Mapping
from typing import cast

import pytest
from legalforecast.evals.live_model_solver import (
    ANTHROPIC_API_KEY_ENV,
    GEMINI_API_KEY_ENV,
    OPENAI_API_KEY_ENV,
)
from legalforecast.labeling.provider_environment import (
    GENERIC_PROVIDER_API_KEY_ENV,
    ProviderEnvironmentError,
    reduce_provider_child_environment,
    run_provider_isolated_command,
)


def _labeling_stage_parent_env() -> dict[str, str]:
    return {
        "PATH": "/reviewed/bin",
        OPENAI_API_KEY_ENV: "openai-parent-fixture",
        ANTHROPIC_API_KEY_ENV: "anthropic-parent-fixture",
        GEMINI_API_KEY_ENV: "google-parent-fixture",
    }


@pytest.mark.parametrize(
    ("provider", "selected_name"),
    [
        ("anthropic", ANTHROPIC_API_KEY_ENV),
        ("google", GEMINI_API_KEY_ENV),
        ("openai", OPENAI_API_KEY_ENV),
    ],
)
def test_reducer_keeps_only_selected_provider_key_for_child_names(
    provider: str,
    selected_name: str,
) -> None:
    child_env = reduce_provider_child_environment(
        provider=provider,
        parent_env=_labeling_stage_parent_env(),
    )

    assert child_env["PATH"] == "/reviewed/bin"
    assert selected_name in child_env
    assert {
        name
        for name in child_env
        if name in {OPENAI_API_KEY_ENV, ANTHROPIC_API_KEY_ENV, GEMINI_API_KEY_ENV}
    } == {selected_name}
    assert GENERIC_PROVIDER_API_KEY_ENV not in child_env


@pytest.mark.parametrize(
    ("provider", "selected_name"),
    [
        ("anthropic", ANTHROPIC_API_KEY_ENV),
        ("google", GEMINI_API_KEY_ENV),
        ("openai", OPENAI_API_KEY_ENV),
    ],
)
def test_runner_passes_only_selected_provider_key_name_to_child(
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    selected_name: str,
) -> None:
    captured: dict[str, Mapping[str, str]] = {}

    def fake_run(
        command: list[str],
        *,
        check: bool,
        env: Mapping[str, str],
    ) -> subprocess.CompletedProcess[str]:
        assert command == ["python", "-V"]
        assert check is False
        captured["env"] = env
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    status = run_provider_isolated_command(
        provider=provider,
        command=("python", "-V"),
        parent_env=_labeling_stage_parent_env(),
    )

    assert status == 0
    child_env = cast(Mapping[str, str], captured["env"])
    assert {
        name
        for name in child_env
        if name in {OPENAI_API_KEY_ENV, ANTHROPIC_API_KEY_ENV, GEMINI_API_KEY_ENV}
    } == {selected_name}
    assert GENERIC_PROVIDER_API_KEY_ENV not in child_env


@pytest.mark.parametrize(
    ("provider", "selected_name"),
    [
        ("anthropic", ANTHROPIC_API_KEY_ENV),
        ("google", GEMINI_API_KEY_ENV),
        ("openai", OPENAI_API_KEY_ENV),
    ],
)
def test_reducer_maps_generic_workflow_key_to_selected_canonical_name(
    provider: str,
    selected_name: str,
) -> None:
    child_env = reduce_provider_child_environment(
        provider=provider,
        parent_env={
            "PATH": "/reviewed/bin",
            GENERIC_PROVIDER_API_KEY_ENV: "workflow-fixture",
        },
    )

    assert child_env["PATH"] == "/reviewed/bin"
    assert {
        name
        for name in child_env
        if name in {OPENAI_API_KEY_ENV, ANTHROPIC_API_KEY_ENV, GEMINI_API_KEY_ENV}
    } == {selected_name}
    assert GENERIC_PROVIDER_API_KEY_ENV not in child_env


def test_reducer_rejects_cross_stage_secret_names_without_logging_values() -> None:
    with pytest.raises(
        ProviderEnvironmentError,
        match=(
            "cross-stage secret environment names are not allowed: "
            "MISTRAL_API_KEY, PACER_PASSWORD"
        ),
    ) as exc_info:
        reduce_provider_child_environment(
            provider="openai",
            parent_env={
                OPENAI_API_KEY_ENV: "openai-parent-fixture",
                "MISTRAL_API_KEY": "mistral-secret-value",
                "PACER_PASSWORD": "pacer-secret-value",
            },
        )

    assert "mistral-secret-value" not in str(exc_info.value)
    assert "pacer-secret-value" not in str(exc_info.value)
