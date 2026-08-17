# pyright: reportPrivateUsage=false

from __future__ import annotations

import pytest
from legalforecast.multiharness.auth_profiles import (
    _PROFILE_INFISICAL_PATH,
    AUTH_PROFILE_IDS,
    CONTRIBUTOR_SUBSCRIPTION,
    CONTRIBUTOR_SUBSCRIPTION_INFISICAL_PATH,
    FIXTURE_NONE,
    HARNESS_RUNTIME_INFISICAL_ROOT,
    LABELING_INFISICAL_PATH,
    LOCAL_CLI_SUBSCRIPTION_CATEGORY,
    PUBLISHED_API_KEY,
    RUN_CLASS_COMMUNITY,
    RUN_CLASS_OFFICIAL,
    AuthProfileError,
    FixtureSubscriptionPresence,
    _require_declared_profile_infisical_path,
    infisical_path_for_profile,
    published_api_key_layout,
    require_auth_profile_for_run_class,
    require_auth_profile_id,
    require_infisical_environment,
    require_local_subscription_presence,
    resolve_auth_profile,
)


def test_canonical_profile_ids_round_trip() -> None:
    for profile_id in (FIXTURE_NONE, PUBLISHED_API_KEY, CONTRIBUTOR_SUBSCRIPTION):
        assert require_auth_profile_id(profile_id) == profile_id


@pytest.mark.parametrize(
    "value",
    (
        None,
        "",
        " fixture-none",
        "fixture_none",
        "explicit_api_key",
        "published_api_key",
        "contributor_subscription",
        "local_cli_subscription",
        "local-cli-subscription",
        "claude-api-automation",
        ["fixture-none", "published-api-key"],
    ),
)
def test_missing_ambiguous_and_alias_profiles_fail_closed(value: object) -> None:
    with pytest.raises(AuthProfileError):
        require_auth_profile_id(value)


def test_fixture_none_never_has_an_infisical_path() -> None:
    resolved = resolve_auth_profile(
        FIXTURE_NONE,
        supported_profiles=(FIXTURE_NONE,),
    )
    assert resolved.infisical_path is None
    assert resolved.projected_env_vars == ()
    assert resolved.public_provenance() == {"auth_profile": FIXTURE_NONE}
    with pytest.raises(AuthProfileError, match="never reads credentials"):
        infisical_path_for_profile(FIXTURE_NONE)


def test_credentialed_profiles_use_declared_infisical_paths() -> None:
    api_key = resolve_auth_profile(
        PUBLISHED_API_KEY,
        supported_profiles=(PUBLISHED_API_KEY, CONTRIBUTOR_SUBSCRIPTION),
        projected_env_vars=("OPENAI_API_KEY",),
    )
    subscription = resolve_auth_profile(
        CONTRIBUTOR_SUBSCRIPTION,
        supported_profiles=(PUBLISHED_API_KEY, CONTRIBUTOR_SUBSCRIPTION),
    )
    assert api_key.infisical_path == LABELING_INFISICAL_PATH
    assert api_key.infisical_path != (
        f"{HARNESS_RUNTIME_INFISICAL_ROOT}/published-api-key"
    )
    assert subscription.infisical_path is None
    assert subscription.projected_env_vars == ()
    assert subscription.public_provenance() == {
        "auth_profile": CONTRIBUTOR_SUBSCRIPTION,
        "auth_category": "local_cli_subscription",
    }
    with pytest.raises(AuthProfileError, match="never reads operator-hosted"):
        infisical_path_for_profile(CONTRIBUTOR_SUBSCRIPTION)
    assert api_key.infisical_path != subscription.infisical_path
    assert "account" not in api_key.public_provenance()
    assert api_key.public_provenance()["auth_profile"] == PUBLISHED_API_KEY
    assert api_key.infisical_env == "dev"
    layout = published_api_key_layout()
    assert layout["infisical_path"] == LABELING_INFISICAL_PATH
    assert layout["canonical_environment"] == "dev"
    assert layout["production_source"] == "github-environment"
    assert "GEMINI_API_KEY" not in str(layout)


def test_contributor_subscription_infisical_leaf_is_reserved_not_wired() -> None:
    """Keep the named contributor leaf out of every live credential lookup.

    ``CONTRIBUTOR_SUBSCRIPTION_INFISICAL_PATH`` exists so a future lookup-table
    edit has a named path to *not* add. This test is the lock: it fails if the
    leaf is ever wired into ``_PROFILE_INFISICAL_PATH``, if the declared-path
    validator starts accepting it, or if any profile resolves to it.
    """

    assert CONTRIBUTOR_SUBSCRIPTION_INFISICAL_PATH == (
        f"{HARNESS_RUNTIME_INFISICAL_ROOT}/contributor-subscription"
    )
    assert set(_PROFILE_INFISICAL_PATH) == {PUBLISHED_API_KEY}
    assert CONTRIBUTOR_SUBSCRIPTION not in _PROFILE_INFISICAL_PATH
    assert CONTRIBUTOR_SUBSCRIPTION_INFISICAL_PATH not in set(
        _PROFILE_INFISICAL_PATH.values()
    )
    with pytest.raises(AuthProfileError, match="declared profile Infisical path"):
        _require_declared_profile_infisical_path(
            CONTRIBUTOR_SUBSCRIPTION_INFISICAL_PATH
        )
    with pytest.raises(AuthProfileError, match="never reads operator-hosted"):
        infisical_path_for_profile(CONTRIBUTOR_SUBSCRIPTION)
    assert published_api_key_layout()["infisical_path"] == LABELING_INFISICAL_PATH
    for profile_id in sorted(AUTH_PROFILE_IDS):
        resolved = resolve_auth_profile(
            profile_id,
            supported_profiles=(profile_id,),
            projected_env_vars=(
                ("OPENAI_API_KEY",) if profile_id == PUBLISHED_API_KEY else None
            ),
        )
        assert resolved.infisical_path != CONTRIBUTOR_SUBSCRIPTION_INFISICAL_PATH


def test_profiles_cannot_silently_substitute() -> None:
    with pytest.raises(AuthProfileError, match="not supported"):
        resolve_auth_profile(
            PUBLISHED_API_KEY,
            supported_profiles=(CONTRIBUTOR_SUBSCRIPTION,),
            projected_env_vars=("OPENAI_API_KEY",),
        )
    with pytest.raises(AuthProfileError, match="never reads credentials"):
        resolve_auth_profile(
            FIXTURE_NONE,
            supported_profiles=(FIXTURE_NONE,),
            projected_env_vars=("OPENAI_API_KEY",),
        )
    with pytest.raises(AuthProfileError, match="projected environment names"):
        resolve_auth_profile(
            PUBLISHED_API_KEY,
            supported_profiles=(PUBLISHED_API_KEY,),
        )
    with pytest.raises(AuthProfileError, match="never exports credentials"):
        resolve_auth_profile(
            CONTRIBUTOR_SUBSCRIPTION,
            supported_profiles=(CONTRIBUTOR_SUBSCRIPTION,),
            projected_env_vars=("CLAUDE_CODE_OAUTH_TOKEN",),
        )


def test_production_infisical_environment_is_refused() -> None:
    with pytest.raises(AuthProfileError, match="GitHub Environment"):
        require_infisical_environment("prod")
    with pytest.raises(AuthProfileError, match="GitHub Environment"):
        resolve_auth_profile(
            PUBLISHED_API_KEY,
            supported_profiles=(PUBLISHED_API_KEY,),
            projected_env_vars=("OPENAI_API_KEY",),
            infisical_env="prod",
        )


def test_contributor_subscription_is_uncredentialed_local_category() -> None:
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
    with pytest.raises(AuthProfileError, match="never exports"):
        resolve_auth_profile(
            CONTRIBUTOR_SUBSCRIPTION,
            supported_profiles=(CONTRIBUTOR_SUBSCRIPTION,),
            projected_env_vars=("CLAUDE_CODE_OAUTH_TOKEN",),
        )


def test_local_cli_subscription_token_is_a_refused_alias() -> None:
    with pytest.raises(AuthProfileError, match="refused alias"):
        require_auth_profile_id(LOCAL_CLI_SUBSCRIPTION_CATEGORY)


def test_contributor_subscription_cannot_be_selected_for_official_runs() -> None:
    with pytest.raises(AuthProfileError, match="official"):
        require_auth_profile_for_run_class(CONTRIBUTOR_SUBSCRIPTION, RUN_CLASS_OFFICIAL)
    assert (
        require_auth_profile_for_run_class(PUBLISHED_API_KEY, RUN_CLASS_OFFICIAL)
        == PUBLISHED_API_KEY
    )
    assert (
        require_auth_profile_for_run_class(
            CONTRIBUTOR_SUBSCRIPTION, RUN_CLASS_COMMUNITY
        )
        == CONTRIBUTOR_SUBSCRIPTION
    )


def test_absent_subscription_presence_refuses_without_fallback() -> None:
    with pytest.raises(AuthProfileError, match="absent"):
        require_local_subscription_presence(parent_env={})
    with pytest.raises(AuthProfileError, match="CI"):
        require_local_subscription_presence(parent_env={"CI": "true"})
    with pytest.raises(AuthProfileError, match="CI"):
        require_local_subscription_presence(parent_env={"GITHUB_ACTIONS": "1"})
    FixtureSubscriptionPresence().prove({})
