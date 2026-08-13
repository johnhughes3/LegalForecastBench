from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from legalforecast.multiharness._infisical_env_extract import (
    ExtractError,
    projected_env_payload,
)
from legalforecast.multiharness.auth_profiles import (
    CONTRIBUTOR_SUBSCRIPTION,
    FIXTURE_NONE,
    PUBLISHED_API_KEY,
    AuthProfileError,
    resolve_auth_profile,
)
from legalforecast.multiharness.local_cli_environment import (
    InfisicalSandboxCredentialSource,
    StaticCredentialSource,
    build_local_cli_environment,
    project_profile_credentials,
)

_CANARY_ENV = {
    "OPENAI_API_KEY": "ambient-openai-canary",
    "ANTHROPIC_API_KEY": "ambient-anthropic-canary",
    "AWS_SECRET_ACCESS_KEY": "ambient-aws-canary",
    "SSH_AUTH_SOCK": "/tmp/ambient-ssh.sock",
    "GPG_AGENT_INFO": "/tmp/ambient-gpg",
    "CLAUDE_CODE_OAUTH_TOKEN": "ambient-subscription-canary",
    "HOME": "/private/operator-home",
    "PATH": "/usr/bin",
    "LC_CTYPE": "C.UTF-8",
}


def test_fixture_none_environment_excludes_ambient_secrets(tmp_path: Path) -> None:
    profile = resolve_auth_profile(FIXTURE_NONE, supported_profiles=(FIXTURE_NONE,))
    scratch = tmp_path / "scratch"
    environment = build_local_cli_environment(
        profile,
        scratch,
        parent_env=_CANARY_ENV,
    )

    assert "OPENAI_API_KEY" not in environment
    assert "ANTHROPIC_API_KEY" not in environment
    assert "AWS_SECRET_ACCESS_KEY" not in environment
    assert "SSH_AUTH_SOCK" not in environment
    assert "GPG_AGENT_INFO" not in environment
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in environment
    assert environment["PATH"] == "/usr/bin"
    assert environment["LC_CTYPE"] == "C.UTF-8"
    assert environment["HOME"] == str(scratch / "adapter-home")
    assert environment["HOME"] != _CANARY_ENV["HOME"]
    assert not (Path(environment["HOME"]) / ".provider-token").exists()
    assert set(environment).issubset(
        {
            "PATH",
            "LC_CTYPE",
            "HOME",
            "XDG_CACHE_HOME",
            "XDG_CONFIG_HOME",
            "XDG_DATA_HOME",
            "XDG_STATE_HOME",
            "TMPDIR",
            "CLAUDE_CONFIG_DIR",
            "CODEX_HOME",
        }
    )


def test_published_api_key_projects_only_declared_credentials(tmp_path: Path) -> None:
    profile = resolve_auth_profile(
        PUBLISHED_API_KEY,
        supported_profiles=(PUBLISHED_API_KEY, CONTRIBUTOR_SUBSCRIPTION),
        projected_env_vars=("OPENAI_API_KEY",),
    )
    projected = project_profile_credentials(
        profile,
        credential_source=StaticCredentialSource(
            {"OPENAI_API_KEY": "projected-openai-key"}
        ),
        parent_env=_CANARY_ENV,
    )
    environment = build_local_cli_environment(
        profile,
        tmp_path / "scratch",
        projected_credentials=projected,
        parent_env=_CANARY_ENV,
    )

    assert environment["OPENAI_API_KEY"] == "projected-openai-key"
    assert "ANTHROPIC_API_KEY" not in environment
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in environment
    assert "AWS_SECRET_ACCESS_KEY" not in environment


def test_profiles_do_not_fall_back_to_host_or_each_other(tmp_path: Path) -> None:
    api_profile = resolve_auth_profile(
        PUBLISHED_API_KEY,
        supported_profiles=(PUBLISHED_API_KEY,),
        projected_env_vars=("OPENAI_API_KEY",),
    )
    with pytest.raises(AuthProfileError, match="host environment"):
        project_profile_credentials(
            api_profile,
            credential_source=StaticCredentialSource(
                {"OPENAI_API_KEY": _CANARY_ENV["OPENAI_API_KEY"]}
            ),
            parent_env=_CANARY_ENV,
        )
    with pytest.raises(AuthProfileError, match="outside the declared profile"):
        project_profile_credentials(
            api_profile,
            credential_source=StaticCredentialSource(
                {
                    "OPENAI_API_KEY": "projected-openai-key",
                    "CLAUDE_CODE_OAUTH_TOKEN": "subscription-should-not-appear",
                }
            ),
            parent_env=_CANARY_ENV,
        )
    fixture = resolve_auth_profile(FIXTURE_NONE, supported_profiles=(FIXTURE_NONE,))
    with pytest.raises(AuthProfileError, match="never reads credentials"):
        project_profile_credentials(
            fixture,
            credential_source=StaticCredentialSource(
                {"OPENAI_API_KEY": "projected-openai-key"}
            ),
            parent_env=_CANARY_ENV,
        )
    with pytest.raises(AuthProfileError, match="never reads credentials"):
        build_local_cli_environment(
            fixture,
            tmp_path / "scratch",
            projected_credentials={"OPENAI_API_KEY": "projected-openai-key"},
            parent_env=_CANARY_ENV,
        )


def test_infisical_source_uses_wrapper_and_refuses_host_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = resolve_auth_profile(
        PUBLISHED_API_KEY,
        supported_profiles=(PUBLISHED_API_KEY,),
        projected_env_vars=("OPENAI_API_KEY",),
    )
    wrapper = tmp_path / "infisical-agent-sandbox"
    wrapper.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    wrapper.chmod(0o700)
    captured: dict[str, object] = {}

    def _run(
        argv: tuple[str, ...], **kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        captured["argv"] = argv
        captured["env"] = kwargs["env"]
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=b'{"OPENAI_API_KEY":"infisical-projected-key"}\n',
            stderr=b"",
        )

    monkeypatch.setattr(
        "legalforecast.multiharness.local_cli_environment.subprocess.run",
        _run,
    )
    source = InfisicalSandboxCredentialSource(
        wrapper_path=wrapper,
        parent_env=_CANARY_ENV,
    )
    values = source.fetch_projected_env(profile)
    argv = captured["argv"]
    assert isinstance(argv, tuple)
    assert Path(argv[0]).name == "infisical-agent-sandbox"
    assert "infisical" not in argv[1:]
    assert "op" not in argv
    assert "--path" in argv
    path_index = argv.index("--path")
    assert str(argv[path_index + 1]).startswith(
        "/agents/sandbox/legalforecastbench/harness-runtime/"
    )
    env = captured["env"]
    assert isinstance(env, dict)
    assert "OPENAI_API_KEY" not in env
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert values == {"OPENAI_API_KEY": "infisical-projected-key"}

    def _run_host_value(
        argv: tuple[str, ...], **_kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=json.dumps(
                {"OPENAI_API_KEY": _CANARY_ENV["OPENAI_API_KEY"]}
            ).encode(),
            stderr=b"",
        )

    monkeypatch.setattr(
        "legalforecast.multiharness.local_cli_environment.subprocess.run",
        _run_host_value,
    )
    with pytest.raises(AuthProfileError, match="host environment"):
        source.fetch_projected_env(profile)

    with pytest.raises(AuthProfileError, match="infisical-agent-sandbox"):
        InfisicalSandboxCredentialSource(
            wrapper_path=tmp_path / "infisical",
            parent_env=_CANARY_ENV,
        ).fetch_projected_env(profile)


def test_infisical_extractor_omits_broker_identity() -> None:
    source = {
        "OPENAI_API_KEY": "projected",
        "INFISICAL_TOKEN": "broker-token",
        "INFISICAL_AGENT_SANDBOX_MACHINE_CLIENT_SECRET": "broker-secret",
    }
    assert projected_env_payload(("OPENAI_API_KEY",), source) == {
        "OPENAI_API_KEY": "projected"
    }
    with pytest.raises(ExtractError, match="broker identity"):
        projected_env_payload(("INFISICAL_TOKEN",), source)
