from __future__ import annotations

import pytest
from legalforecast.multiharness.auth_profiles import (
    CONTRIBUTOR_SUBSCRIPTION,
    FIXTURE_NONE,
    HARNESS_RUNTIME_INFISICAL_ROOT,
    PUBLISHED_API_KEY,
    AuthProfileError,
    infisical_path_for_profile,
    require_auth_profile_id,
    require_infisical_environment,
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


def test_credentialed_profiles_use_harness_runtime_infisical_paths() -> None:
    api_key = resolve_auth_profile(
        PUBLISHED_API_KEY,
        supported_profiles=(PUBLISHED_API_KEY, CONTRIBUTOR_SUBSCRIPTION),
        projected_env_vars=("OPENAI_API_KEY",),
    )
    subscription = resolve_auth_profile(
        CONTRIBUTOR_SUBSCRIPTION,
        supported_profiles=(PUBLISHED_API_KEY, CONTRIBUTOR_SUBSCRIPTION),
        projected_env_vars=("CLAUDE_CODE_OAUTH_TOKEN",),
    )
    assert api_key.infisical_path == (
        f"{HARNESS_RUNTIME_INFISICAL_ROOT}/published-api-key"
    )
    assert subscription.infisical_path == (
        f"{HARNESS_RUNTIME_INFISICAL_ROOT}/contributor-subscription"
    )
    assert api_key.infisical_path != subscription.infisical_path
    assert "account" not in api_key.public_provenance()
    assert api_key.public_provenance()["auth_profile"] == PUBLISHED_API_KEY


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


def test_production_infisical_environment_is_refused() -> None:
    with pytest.raises(AuthProfileError, match="production"):
        require_infisical_environment("prod")
    with pytest.raises(AuthProfileError):
        resolve_auth_profile(
            PUBLISHED_API_KEY,
            supported_profiles=(PUBLISHED_API_KEY,),
            projected_env_vars=("OPENAI_API_KEY",),
            infisical_env="prod",
        )
