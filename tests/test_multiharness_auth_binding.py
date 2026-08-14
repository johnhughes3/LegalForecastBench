"""Bind approved auth profiles to adapter manifests and child environments."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from legalforecast.multiharness.auth_binding import (
    ADAPTER_BOUND_AUTH_PROFILES,
    bind_adapter_auth_profile,
    contained_execution_service,
    expected_bound_child_environment_names,
    project_bound_child_environment,
    require_execution_service_profile,
)
from legalforecast.multiharness.auth_profiles import (
    CONTRIBUTOR_SUBSCRIPTION,
    FIXTURE_NONE,
    HARNESS_RUNTIME_INFISICAL_ROOT,
    INFISICAL_WRAPPER_NAME,
    PUBLISHED_API_KEY,
    AuthProfileError,
    published_api_key_layout,
)
from legalforecast.multiharness.claude_code import (
    ClaudeCodeCliAdapter,
    ClaudeCodeCliAdapterError,
    build_claude_invocation_plan,
    claude_code_local_manifest,
)
from legalforecast.multiharness.codex_cli import (
    CodexCliAdapter,
    CodexCliAdapterError,
    build_codex_invocation_plan,
    load_codex_local_cli_manifest,
)
from legalforecast.multiharness.local_cli_contracts import (
    FakeLocalCliExecutionService,
    FixtureTranscript,
)
from legalforecast.multiharness.local_cli_environment import StaticCredentialSource
from legalforecast.multiharness.local_cli_manifest import LocalCliAdapterManifest
from legalforecast.multiharness.spec import (
    AdapterManifest,
    CanonicalTask,
    RunRequest,
    SandboxPolicy,
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
    "OP_SERVICE_ACCOUNT_TOKEN": "canary-op-token-value",
    "CANARY_AWS_KEY": "canary-aws-key-value",
}


def _polluted_parent_env() -> dict[str, str]:
    parent = dict(_CANARY_ENV)
    for index in range(20):
        parent[f"CANARY_RAND_{index:02d}"] = f"random-canary-{index:02d}"
    return parent


def test_published_api_key_layout_names_wrapper_path_and_keys() -> None:
    layout = published_api_key_layout()
    assert layout["wrapper"] == INFISICAL_WRAPPER_NAME
    assert layout["infisical_path"] == (
        f"{HARNESS_RUNTIME_INFISICAL_ROOT}/published-api-key"
    )
    assert layout["fail_closed_when_empty"] is True
    assert layout["host_environment_fallback"] is False
    keys = {(item["executable"], item["name"]) for item in layout["infisical_keys"]}
    assert keys == {("claude", "ANTHROPIC_API_KEY"), ("codex", "OPENAI_API_KEY")}
    assert "prod" not in layout["allowed_environments"]
    docs = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "adapters"
        / "published-api-key-profile.md"
    ).read_text(encoding="utf-8")
    assert str(layout["infisical_path"]) in docs
    assert INFISICAL_WRAPPER_NAME in docs
    assert "ANTHROPIC_API_KEY" in docs
    assert "OPENAI_API_KEY" in docs
    docs = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "adapters"
        / "published-api-key-profile.md"
    ).read_text(encoding="utf-8")
    assert str(layout["infisical_path"]) in docs
    assert str(layout["wrapper"]) in docs
    for _executable, name in keys:
        assert f"`{name}`" in docs


def test_shipped_manifests_match_published_api_key_layout() -> None:
    claude = bind_adapter_auth_profile(claude_code_local_manifest(), PUBLISHED_API_KEY)
    codex = bind_adapter_auth_profile(
        load_codex_local_cli_manifest(), PUBLISHED_API_KEY
    )
    assert claude.profile.projected_env_vars == ("ANTHROPIC_API_KEY",)
    assert codex.profile.projected_env_vars == ("OPENAI_API_KEY",)
    assert claude.profile.infisical_path == codex.profile.infisical_path
    assert claude.profile.public_provenance() == {"auth_profile": PUBLISHED_API_KEY}
    assert claude.profile.infisical_path not in str(claude.profile.public_provenance())


def test_fixture_none_binds_with_zero_credentials(tmp_path: Path) -> None:
    bound = bind_adapter_auth_profile(claude_code_local_manifest(), FIXTURE_NONE)
    assert bound.profile_id == FIXTURE_NONE
    assert bound.profile.projected_env_vars == ()
    assert bound.profile.infisical_path is None
    environment = project_bound_child_environment(
        bound,
        tmp_path / "scratch",
        credential_source=None,
        parent_env=_polluted_parent_env(),
    )
    allowed = expected_bound_child_environment_names(
        bound, parent_env=_polluted_parent_env()
    )
    assert set(environment) == allowed
    assert "ANTHROPIC_API_KEY" not in environment
    assert "OPENAI_API_KEY" not in environment
    assert ADAPTER_BOUND_AUTH_PROFILES == frozenset({FIXTURE_NONE, PUBLISHED_API_KEY})


@pytest.mark.parametrize(
    ("manifest_loader", "secret_name", "secret_value"),
    (
        (claude_code_local_manifest, "ANTHROPIC_API_KEY", "projected-anthropic-key"),
        (load_codex_local_cli_manifest, "OPENAI_API_KEY", "projected-openai-key"),
    ),
)
def test_published_api_key_child_env_equals_allowlist_union_projected(
    tmp_path: Path,
    manifest_loader: Callable[[], LocalCliAdapterManifest],
    secret_name: str,
    secret_value: str,
) -> None:
    bound = bind_adapter_auth_profile(manifest_loader(), PUBLISHED_API_KEY)
    parent = _polluted_parent_env()
    environment = project_bound_child_environment(
        bound,
        tmp_path / "scratch",
        credential_source=StaticCredentialSource({secret_name: secret_value}),
        parent_env=parent,
    )
    allowed = expected_bound_child_environment_names(bound, parent_env=parent)
    assert set(environment) == allowed
    assert environment[secret_name] == secret_value
    assert environment[secret_name] != parent[secret_name]
    for name, value in parent.items():
        if name in allowed:
            continue
        assert name not in environment
        assert value not in environment.values()


@pytest.mark.parametrize(
    "requested",
    (
        None,
        "",
        "fixture_none",
        "explicit_api_key",
        "published_api_key",
        "not-a-profile",
        CONTRIBUTOR_SUBSCRIPTION,
    ),
)
def test_forbidden_and_unknown_profiles_refuse_at_plan_time(requested: object) -> None:
    with pytest.raises((AuthProfileError, ClaudeCodeCliAdapterError)):
        bind_adapter_auth_profile(claude_code_local_manifest(), requested)
    with pytest.raises(ClaudeCodeCliAdapterError):
        build_claude_invocation_plan(
            prompt="prompt",
            model="claude-sonnet-4-6",
            required_unit_ids=("count_i",),
            workspace=Path("workspace"),
            output_schema_path=Path("workspace") / "output-schema.json",
            auth_profile=requested,
        )
    with pytest.raises(CodexCliAdapterError):
        build_codex_invocation_plan(
            _codex_request(),
            Path("workspace"),
            prompt="solve fixture",
            auth_profile=requested,
        )


def test_claude_and_codex_plans_record_bound_profile() -> None:
    claude = build_claude_invocation_plan(
        prompt="prompt",
        model="claude-sonnet-4-6",
        required_unit_ids=("count_i",),
        workspace=Path("workspace"),
        output_schema_path=Path("workspace") / "output-schema.json",
        auth_profile=PUBLISHED_API_KEY,
    )
    assert claude.auth_profile == PUBLISHED_API_KEY
    fixture = build_claude_invocation_plan(
        prompt="prompt",
        model="claude-sonnet-4-6",
        required_unit_ids=("count_i",),
        workspace=Path("workspace"),
        output_schema_path=Path("workspace") / "output-schema.json",
    )
    assert fixture.auth_profile == FIXTURE_NONE
    codex = build_codex_invocation_plan(
        _codex_request(),
        Path("workspace"),
        prompt="solve fixture",
        auth_profile=PUBLISHED_API_KEY,
    )
    assert codex.auth_profile == PUBLISHED_API_KEY
    assert "auth.json" not in "".join(codex.argv)
    assert codex.public_config()["auth_profile"] == PUBLISHED_API_KEY


def test_fake_service_cannot_claim_published_api_key(tmp_path: Path) -> None:
    fake = FakeLocalCliExecutionService(FixtureTranscript(stdout="{}"))
    with pytest.raises(AuthProfileError, match="contained execution service"):
        require_execution_service_profile(fake, PUBLISHED_API_KEY)
    require_execution_service_profile(fake, FIXTURE_NONE)
    with pytest.raises(ClaudeCodeCliAdapterError, match="contained execution service"):
        ClaudeCodeCliAdapter(
            execution_service=fake,
            auth_profile=PUBLISHED_API_KEY,
        ).prepare(_claude_request(), tmp_path / "claude-workspace")
    with pytest.raises(CodexCliAdapterError, match="contained execution service"):
        CodexCliAdapter(
            execution_service=fake,
            auth_profile=PUBLISHED_API_KEY,
        ).run(_codex_request(), tmp_path / "codex-workspace")


def test_contained_service_defaults_to_infisical_wrapper_for_published_api_key() -> (
    None
):
    bound = bind_adapter_auth_profile(claude_code_local_manifest(), PUBLISHED_API_KEY)
    service = contained_execution_service(bound)
    assert service.auth_profile == PUBLISHED_API_KEY
    assert service.credential_source is not None
    assert (
        type(service.credential_source).__name__ == "InfisicalSandboxCredentialSource"
    )
    fixture = bind_adapter_auth_profile(claude_code_local_manifest(), FIXTURE_NONE)
    fixture_service = contained_execution_service(fixture)
    assert fixture_service.credential_source is None
    with pytest.raises(AuthProfileError, match="never reads credentials"):
        contained_execution_service(
            fixture,
            credential_source=StaticCredentialSource({"ANTHROPIC_API_KEY": "x"}),
        )


def test_published_api_key_empty_projection_fails_closed(tmp_path: Path) -> None:
    bound = bind_adapter_auth_profile(claude_code_local_manifest(), PUBLISHED_API_KEY)
    with pytest.raises(AuthProfileError, match="unavailable"):
        project_bound_child_environment(
            bound,
            tmp_path / "scratch",
            credential_source=StaticCredentialSource({}),
            parent_env=_CANARY_ENV,
        )


def _claude_request() -> RunRequest:
    return RunRequest(
        request_id="request-1",
        task=CanonicalTask(
            task_id="lfb:case-1:full_packet",
            family="legalforecast_mtd",
            scoring_mode="lfb_brier",
            suite_version="legalforecast-mtd-v1",
            source_id="case-1",
            task_sha256="sha256:" + "1" * 64,
            metadata={"required_unit_ids": ["count_i"], "solver_prompt": "prompt"},
        ),
        adapter=AdapterManifest(
            adapter_id="claude-code-clean-native",
            display_name="Claude Code",
            adapter_version="1.0.0",
            command=("legalforecast.multiharness.claude_code:ClaudeCodeCliAdapter",),
        ),
        model_key="anthropic:claude-sonnet-4-6",
        sandbox_policy=SandboxPolicy(
            policy_id="offline-cli",
            backend="none",
            image="none",
            network_policy="none",
            timeout_seconds=30,
        ),
        request_sha256="sha256:" + "3" * 64,
    )


def _codex_request() -> RunRequest:
    return RunRequest(
        request_id="request-1",
        task=CanonicalTask(
            task_id="lfb:case-1:full_packet",
            family="legalforecast_mtd",
            scoring_mode="lfb_brier",
            suite_version="fixture",
            source_id="case-1",
            task_sha256="sha256:" + "1" * 64,
            metadata={"prompt": "solve fixture"},
        ),
        adapter=AdapterManifest(
            adapter_id="codex-cli-offline",
            display_name="Codex CLI Offline Adapter",
            adapter_version="0.1.0",
            command=("python", "-m", "legalforecast.multiharness.codex_cli_cli"),
        ),
        model_key="codex:gpt-5.1",
        sandbox_policy=SandboxPolicy(
            policy_id="fixture",
            backend="docker",
            image="python:3.12-slim",
            network_policy="provider_egress_host_only",
            timeout_seconds=30,
            working_directory="/workspace",
        ),
        request_sha256="sha256:" + "2" * 64,
    )
