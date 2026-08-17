# pyright: reportPrivateUsage=false

"""Contributor-owned local_cli_subscription profile (dm0g.4.2.14)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
from legalforecast.multiharness.auth_binding import (
    bind_adapter_auth_profile,
    bind_official_run_auth_profile,
    contained_execution_service,
    project_bound_child_environment,
)
from legalforecast.multiharness.auth_profiles import (
    _PROFILE_INFISICAL_PATH,
    AUTH_PROFILE_IDS,
    CONTRIBUTOR_SUBSCRIPTION,
    CONTRIBUTOR_SUBSCRIPTION_INFISICAL_PATH,
    FIXTURE_NONE,
    HARNESS_RUNTIME_INFISICAL_ROOT,
    LABELING_INFISICAL_PATH,
    LOCAL_CLI_SUBSCRIPTION_CATEGORY,
    OFFICIAL_AUTH_PROFILES,
    PUBLISHED_API_KEY,
    RUN_CLASS_OFFICIAL,
    AuthProfileError,
    FixtureSubscriptionPresence,
    infisical_path_for_profile,
    require_auth_profile_for_run_class,
    require_local_subscription_presence,
    resolve_auth_profile,
)
from legalforecast.multiharness.claude_code import (
    build_claude_invocation_plan,
    claude_code_local_manifest,
)
from legalforecast.multiharness.codex_cli import (
    build_codex_invocation_plan,
)
from legalforecast.multiharness.contributor_boundary import LINUX_LANDLOCK_FS_SCOPE
from legalforecast.multiharness.local_cli_environment import StaticCredentialSource
from legalforecast.multiharness.local_cli_identity import executable_pin_for
from legalforecast.multiharness.local_cli_runtime import (
    LocalCliAdapterManifest,
    LocalCliRunSpec,
    LocalCliRuntimeError,
    execute_local_cli,
)
from legalforecast.multiharness.spec import (
    AdapterManifest,
    CanonicalTask,
    RunRequest,
    SandboxPolicy,
)

_FAKE_CLI = Path(__file__).resolve().parent / "fixtures" / "local_cli_fake_cli.py"
_CANARY_ENV = {
    "OPENAI_API_KEY": "ambient-openai-canary",
    "ANTHROPIC_API_KEY": "ambient-anthropic-canary",
    "CLAUDE_CODE_OAUTH_TOKEN": "ambient-subscription-canary",
    "HOME": "/private/operator-home",
    "PATH": os.environ.get("PATH", "/usr/bin"),
    "LC_CTYPE": "C.UTF-8",
}


def test_public_provenance_records_only_the_nonsecret_category() -> None:
    resolved = resolve_auth_profile(
        CONTRIBUTOR_SUBSCRIPTION,
        supported_profiles=(CONTRIBUTOR_SUBSCRIPTION,),
    )
    assert resolved.infisical_path is None
    assert resolved.projected_env_vars == ()
    assert resolved.public_provenance() == {
        "auth_profile": CONTRIBUTOR_SUBSCRIPTION,
        "auth_category": LOCAL_CLI_SUBSCRIPTION_CATEGORY,
    }
    with pytest.raises(AuthProfileError, match="never reads operator-hosted"):
        infisical_path_for_profile(CONTRIBUTOR_SUBSCRIPTION)
    # The reserved harness-runtime leaf is documentation only. It must never
    # become a live lookup and must never reach a public record.
    assert CONTRIBUTOR_SUBSCRIPTION not in _PROFILE_INFISICAL_PATH
    assert CONTRIBUTOR_SUBSCRIPTION_INFISICAL_PATH not in set(
        _PROFILE_INFISICAL_PATH.values()
    )
    assert CONTRIBUTOR_SUBSCRIPTION_INFISICAL_PATH not in json.dumps(
        resolved.public_provenance()
    )


def test_reserved_contributor_infisical_leaf_is_never_a_live_lookup() -> None:
    """The reserved leaf documents a path to never add, not one to resolve."""

    assert CONTRIBUTOR_SUBSCRIPTION_INFISICAL_PATH.startswith(
        f"{HARNESS_RUNTIME_INFISICAL_ROOT}/"
    )
    live_paths: set[str] = set()
    for profile_id in sorted(AUTH_PROFILE_IDS):
        try:
            live_paths.add(infisical_path_for_profile(profile_id))
        except AuthProfileError:
            continue
    # published-api-key is the only profile that resolves to a live path, so a
    # future lookup-table edit that wires up the reserved leaf fails here.
    assert live_paths == {LABELING_INFISICAL_PATH}
    assert CONTRIBUTOR_SUBSCRIPTION_INFISICAL_PATH not in live_paths
    resolved = resolve_auth_profile(
        CONTRIBUTOR_SUBSCRIPTION,
        supported_profiles=(CONTRIBUTOR_SUBSCRIPTION,),
    )
    assert resolved.infisical_path is None


def test_unknown_absent_and_ci_presence_fail_closed_without_fallback() -> None:
    with pytest.raises(AuthProfileError, match="unsupported in CI"):
        require_local_subscription_presence(parent_env={"CI": "true"})
    with pytest.raises(AuthProfileError, match="unsupported in CI"):
        require_local_subscription_presence(parent_env={"GITHUB_ACTIONS": "1"})
    with pytest.raises(AuthProfileError, match="absent; no fallback"):
        require_local_subscription_presence(parent_env={"PATH": "/usr/bin"})
    require_local_subscription_presence(
        parent_env={"CI": "true"},
        presence=FixtureSubscriptionPresence(),
    )


def test_official_runs_cannot_select_contributor_subscription() -> None:
    assert OFFICIAL_AUTH_PROFILES == frozenset({PUBLISHED_API_KEY})
    with pytest.raises(AuthProfileError, match="official"):
        require_auth_profile_for_run_class(CONTRIBUTOR_SUBSCRIPTION, RUN_CLASS_OFFICIAL)
    with pytest.raises(AuthProfileError, match="official"):
        require_auth_profile_for_run_class(FIXTURE_NONE, RUN_CLASS_OFFICIAL)
    with pytest.raises(AuthProfileError, match="official"):
        bind_official_run_auth_profile(
            claude_code_local_manifest(), CONTRIBUTOR_SUBSCRIPTION
        )
    with pytest.raises(AuthProfileError, match="official"):
        bind_adapter_auth_profile(
            claude_code_local_manifest(),
            CONTRIBUTOR_SUBSCRIPTION,
            run_class=RUN_CLASS_OFFICIAL,
        )
    bound = bind_official_run_auth_profile(
        claude_code_local_manifest(), PUBLISHED_API_KEY
    )
    assert bound.profile_id == PUBLISHED_API_KEY


def test_community_bind_does_not_export_manifest_oauth_names(
    tmp_path: Path,
) -> None:
    bound = bind_adapter_auth_profile(
        claude_code_local_manifest(), CONTRIBUTOR_SUBSCRIPTION
    )
    assert bound.profile_id == CONTRIBUTOR_SUBSCRIPTION
    assert bound.profile.projected_env_vars == ()
    assert bound.profile.infisical_path is None
    environment = project_bound_child_environment(
        bound,
        tmp_path / "scratch",
        credential_source=None,
        parent_env=_CANARY_ENV,
    )
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in environment
    assert "ANTHROPIC_API_KEY" not in environment
    assert environment["HOME"] != _CANARY_ENV["HOME"]
    with pytest.raises(AuthProfileError, match="never reads credentials"):
        contained_execution_service(
            bound,
            credential_source=StaticCredentialSource(
                {"CLAUDE_CODE_OAUTH_TOKEN": "must-not-project"}
            ),
        )
    service = contained_execution_service(
        bound,
        subscription_presence=FixtureSubscriptionPresence(),
    )
    assert service.credential_source is None
    assert service.env_vars_for_profile(CONTRIBUTOR_SUBSCRIPTION) == ()


def test_community_plans_accept_contributor_subscription() -> None:
    claude = build_claude_invocation_plan(
        prompt="prompt",
        model="claude-sonnet-4-6",
        required_unit_ids=("count_i",),
        workspace=Path("workspace"),
        output_schema_path=Path("workspace") / "output-schema.json",
        auth_profile=CONTRIBUTOR_SUBSCRIPTION,
    )
    assert claude.auth_profile == CONTRIBUTOR_SUBSCRIPTION
    codex = build_codex_invocation_plan(
        _codex_request(),
        Path("workspace"),
        prompt="solve fixture",
        auth_profile=CONTRIBUTOR_SUBSCRIPTION,
    )
    assert codex.auth_profile == CONTRIBUTOR_SUBSCRIPTION
    assert codex.public_config()["auth_profile"] == CONTRIBUTOR_SUBSCRIPTION


def test_execute_refuses_absent_login_and_never_projects_subscription_token(
    tmp_path: Path,
) -> None:
    spec = _subscription_spec("dump-env")
    with pytest.raises(LocalCliRuntimeError, match="absent; no fallback"):
        execute_local_cli(
            spec,
            tmp_path / "absent",
            parent_env=_CANARY_ENV,
        )
    with pytest.raises(LocalCliRuntimeError, match="unsupported in CI"):
        execute_local_cli(
            spec,
            tmp_path / "ci",
            parent_env={**_CANARY_ENV, "CI": "true"},
        )
    result = execute_local_cli(
        spec,
        tmp_path / "present",
        parent_env=_CANARY_ENV,
        subscription_presence=FixtureSubscriptionPresence(),
    )
    captured = json.loads(result.stdout.decode("utf-8"))
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in captured
    assert "ANTHROPIC_API_KEY" not in captured
    assert captured.get("HOME") != _CANARY_ENV["HOME"]
    assert "ambient-subscription-canary" not in captured.values()
    public = result.to_public_record()
    assert public["auth_profile"] == CONTRIBUTOR_SUBSCRIPTION
    assert public["auth_category"] == LOCAL_CLI_SUBSCRIPTION_CATEGORY
    assert "ambient-subscription-canary" not in json.dumps(public)


def _subscription_spec(mode: str) -> LocalCliRunSpec:
    path = _FAKE_CLI.resolve()
    return LocalCliRunSpec(
        spec_id=f"contributor-{mode}",
        manifest=LocalCliAdapterManifest(
            adapter_id="fixture-cli",
            display_name="Fixture CLI",
            adapter_version="0.1.0",
            command=(sys.executable, str(path)),
            executable=executable_pin_for(path, version="0.1.0"),
            supported_auth_profiles=(CONTRIBUTOR_SUBSCRIPTION,),
            version_probe_args=("--mode", "version"),
        ),
        auth_profile=CONTRIBUTOR_SUBSCRIPTION,
        extra_args=("--mode", mode),
        filesystem_scope=LINUX_LANDLOCK_FS_SCOPE,
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
