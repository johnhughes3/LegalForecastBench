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
    expected_child_environment_names,
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
    assert (scratch.resolve().stat().st_mode & 0o777) == 0o700
    assert set(environment) == expected_child_environment_names(parent_env=_CANARY_ENV)


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
    assert env.get("TERM") == "dumb"
    assert env["HOME"] == _CANARY_ENV["HOME"]
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


def _polluted_parent_env() -> dict[str, str]:
    parent = dict(_CANARY_ENV)
    parent["CANARY_AWS_KEY"] = "canary-aws-key-value"
    parent["ANTHROPIC_API_KEY"] = "canary"
    parent["OP_SERVICE_ACCOUNT_TOKEN"] = "canary-op-token-value"
    for index in range(20):
        parent[f"CANARY_RAND_{index:02d}"] = f"random-canary-{index:02d}"
    return parent


def test_child_env_equals_allowlist_union_projected_against_polluted_parent(
    tmp_path: Path,
) -> None:
    parent = _polluted_parent_env()
    profile = resolve_auth_profile(
        PUBLISHED_API_KEY,
        supported_profiles=(PUBLISHED_API_KEY,),
        projected_env_vars=("OPENAI_API_KEY",),
    )
    projected = {"OPENAI_API_KEY": "projected-openai-key"}
    environment = build_local_cli_environment(
        profile,
        tmp_path / "scratch",
        projected_credentials=projected,
        parent_env=parent,
    )
    allowed = expected_child_environment_names(
        parent_env=parent,
        projected_names=("OPENAI_API_KEY",),
    )
    assert set(environment) == allowed
    assert environment["OPENAI_API_KEY"] == "projected-openai-key"
    assert environment["OPENAI_API_KEY"] != parent["OPENAI_API_KEY"]
    for name, value in parent.items():
        if name in allowed:
            continue
        assert name not in environment
        assert value not in environment.values()


def test_empty_or_partial_infisical_projection_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = resolve_auth_profile(
        PUBLISHED_API_KEY,
        supported_profiles=(PUBLISHED_API_KEY,),
        projected_env_vars=("OPENAI_API_KEY", "ANTHROPIC_API_KEY"),
    )
    wrapper = tmp_path / "infisical-agent-sandbox"
    wrapper.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    wrapper.chmod(0o700)
    source = InfisicalSandboxCredentialSource(
        wrapper_path=wrapper,
        parent_env=_CANARY_ENV,
    )

    def _empty(
        argv: tuple[str, ...], **_kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(argv, 0, stdout=b"{}\n", stderr=b"")

    monkeypatch.setattr(
        "legalforecast.multiharness.local_cli_environment.subprocess.run",
        _empty,
    )
    with pytest.raises(AuthProfileError, match="unavailable") as empty_exc:
        source.fetch_projected_env(profile)
    _assert_no_canaries(str(empty_exc.value))

    def _partial(
        argv: tuple[str, ...], **_kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=b'{"OPENAI_API_KEY":"only-one"}\n',
            stderr=b"",
        )

    monkeypatch.setattr(
        "legalforecast.multiharness.local_cli_environment.subprocess.run",
        _partial,
    )
    with pytest.raises(AuthProfileError, match="unavailable") as partial_exc:
        source.fetch_projected_env(profile)
    _assert_no_canaries(str(partial_exc.value))
    with pytest.raises(AuthProfileError):
        project_profile_credentials(
            profile,
            credential_source=StaticCredentialSource({"OPENAI_API_KEY": "only-one"}),
            parent_env=_CANARY_ENV,
        )


def test_errors_do_not_echo_canary_values() -> None:
    profile = resolve_auth_profile(
        PUBLISHED_API_KEY,
        supported_profiles=(PUBLISHED_API_KEY,),
        projected_env_vars=("OPENAI_API_KEY",),
    )
    with pytest.raises(AuthProfileError) as exc:
        project_profile_credentials(
            profile,
            credential_source=StaticCredentialSource(
                {"OPENAI_API_KEY": _CANARY_ENV["OPENAI_API_KEY"]}
            ),
            parent_env=_polluted_parent_env(),
        )
    _assert_no_canaries(str(exc.value))
    with pytest.raises(AuthProfileError) as missing:
        resolve_auth_profile(
            "does-not-exist",
            supported_profiles=(PUBLISHED_API_KEY,),
            projected_env_vars=("OPENAI_API_KEY",),
        )
    _assert_no_canaries(str(missing.value))


def test_projected_credentials_cannot_shadow_managed_runtime_vars(
    tmp_path: Path,
) -> None:
    profile = resolve_auth_profile(
        PUBLISHED_API_KEY,
        supported_profiles=(PUBLISHED_API_KEY,),
        projected_env_vars=("HOME",),
    )
    with pytest.raises(AuthProfileError, match="host-managed runtime"):
        build_local_cli_environment(
            profile,
            tmp_path / "scratch",
            projected_credentials={"HOME": "/leaked-home"},
            parent_env=_CANARY_ENV,
        )


def test_scratch_root_symlink_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "real"
    target.mkdir()
    scratch = tmp_path / "scratch"
    scratch.symlink_to(target)
    profile = resolve_auth_profile(FIXTURE_NONE, supported_profiles=(FIXTURE_NONE,))
    with pytest.raises(AuthProfileError, match="symlink"):
        build_local_cli_environment(profile, scratch, parent_env=_CANARY_ENV)


def _assert_no_canaries(text: str) -> None:
    parent = _polluted_parent_env()
    for value in parent.values():
        if value in {"/usr/bin", "C.UTF-8"}:
            continue
        assert value not in text
