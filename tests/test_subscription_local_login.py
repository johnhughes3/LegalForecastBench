"""Real contributor-subscription presence proving (multiharness F1).

Every test passes an explicit ``parent_env`` with no ``CI``/``GITHUB_ACTIONS``
keys, because CI itself sets both and an inherited environment would make the
noninteractive refusal fire everywhere.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
from legalforecast.multiharness.auth_profiles import (
    AuthProfileError,
    SubscriptionPresence,
    require_local_subscription_presence,
)
from legalforecast.multiharness.subscription import (
    HARNESS_LOGIN_DESCRIPTORS,
    HarnessLoginDescriptor,
    LocalLoginPresence,
    descriptor_for_executable,
    local_login_presence_for,
)

_BASENAMES = tuple(sorted(HARNESS_LOGIN_DESCRIPTORS))
_DESCRIPTORS = tuple(HARNESS_LOGIN_DESCRIPTORS[basename] for basename in _BASENAMES)


def _parent_env(home: Path, **extra: str) -> dict[str, str]:
    return {"HOME": str(home), "PATH": "/usr/bin", **extra}


def _absent_message(descriptor: HarnessLoginDescriptor) -> str:
    return (
        f"contributor-subscription local login is absent for "
        f"{descriptor.executable_basename!r}; {descriptor.login_hint} on "
        "this host. No fallback."
    )


def _make_login_tree(
    home: Path, descriptor: HarnessLoginDescriptor, *, contents: bytes = b"opaque"
) -> Path:
    config_dir = home / descriptor.home_relative_config_dir
    config_dir.mkdir(parents=True)
    for relative in descriptor.credential_relative_paths:
        artifact = config_dir / relative
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_bytes(contents)
    return config_dir


def test_every_declared_harness_proves_against_its_own_login_tree(
    tmp_path: Path,
) -> None:
    for basename in _BASENAMES:
        home = tmp_path / f"home-{basename}"
        home.mkdir()
        _make_login_tree(home, descriptor_for_executable(basename))
        local_login_presence_for(basename).prove(_parent_env(home))


def test_declared_harnesses_are_exactly_the_characterized_five() -> None:
    assert set(HARNESS_LOGIN_DESCRIPTORS) == {
        "agy",
        "claude",
        "codex",
        "grok",
        "kimi",
    }
    for basename, descriptor in HARNESS_LOGIN_DESCRIPTORS.items():
        assert descriptor.executable_basename == basename
        assert descriptor.credential_relative_paths
        for relative in descriptor.credential_relative_paths:
            assert not Path(relative).is_absolute()
    with pytest.raises(AuthProfileError, match="no local-login layout"):
        descriptor_for_executable("gemini")


def test_ci_and_github_actions_are_refused_even_with_a_real_login_present(
    tmp_path: Path,
) -> None:
    _make_login_tree(tmp_path, descriptor_for_executable("codex"))
    presence = local_login_presence_for("codex")
    for name, value in (("CI", "true"), ("GITHUB_ACTIONS", "1"), ("CI", " YES ")):
        with pytest.raises(AuthProfileError, match="unsupported in CI"):
            presence.prove(_parent_env(tmp_path, **{name: value}))


def test_injected_prover_closes_the_ci_bypass_a_fixture_presence_leaves_open(
    tmp_path: Path,
) -> None:
    _make_login_tree(tmp_path, descriptor_for_executable("claude"))
    presence: SubscriptionPresence = local_login_presence_for("claude")
    require_local_subscription_presence(
        parent_env=_parent_env(tmp_path), presence=presence
    )
    with pytest.raises(AuthProfileError, match="unsupported in CI"):
        require_local_subscription_presence(
            parent_env=_parent_env(tmp_path, CI="true"), presence=presence
        )


@pytest.mark.parametrize("basename", _BASENAMES)
def test_missing_config_directory_fails_closed(basename: str, tmp_path: Path) -> None:
    with pytest.raises(AuthProfileError) as caught:
        local_login_presence_for(basename).prove(_parent_env(tmp_path))
    assert str(caught.value) == _absent_message(descriptor_for_executable(basename))


def test_symlinked_config_directory_is_refused(tmp_path: Path) -> None:
    descriptor = descriptor_for_executable("codex")
    real_home = tmp_path / "real-home"
    real_home.mkdir()
    _make_login_tree(real_home, descriptor)
    fake_home = tmp_path / "fake-home"
    fake_home.mkdir()
    (fake_home / descriptor.home_relative_config_dir).symlink_to(
        real_home / descriptor.home_relative_config_dir, target_is_directory=True
    )
    with pytest.raises(AuthProfileError) as caught:
        local_login_presence_for("codex").prove(_parent_env(fake_home))
    assert str(caught.value) == _absent_message(descriptor)


def test_absent_empty_symlinked_and_nonregular_artifacts_are_each_refused(
    tmp_path: Path,
) -> None:
    descriptor = descriptor_for_executable("codex")
    relative = descriptor.credential_relative_paths[0]
    presence = local_login_presence_for("codex")
    expected = _absent_message(descriptor)

    absent_home = tmp_path / "absent"
    (absent_home / descriptor.home_relative_config_dir).mkdir(parents=True)
    with pytest.raises(AuthProfileError) as caught:
        presence.prove(_parent_env(absent_home))
    assert str(caught.value) == expected

    empty_home = tmp_path / "empty"
    empty_home.mkdir()
    _make_login_tree(empty_home, descriptor, contents=b"")
    with pytest.raises(AuthProfileError) as caught:
        presence.prove(_parent_env(empty_home))
    assert str(caught.value) == expected

    linked_home = tmp_path / "linked"
    config_dir = linked_home / descriptor.home_relative_config_dir
    config_dir.mkdir(parents=True)
    elsewhere = tmp_path / "elsewhere.json"
    elsewhere.write_bytes(b"opaque")
    (config_dir / relative).symlink_to(elsewhere)
    with pytest.raises(AuthProfileError) as caught:
        presence.prove(_parent_env(linked_home))
    assert str(caught.value) == expected

    directory_home = tmp_path / "directory"
    (directory_home / descriptor.home_relative_config_dir / relative).mkdir(
        parents=True
    )
    with pytest.raises(AuthProfileError) as caught:
        presence.prove(_parent_env(directory_home))
    assert str(caught.value) == expected


@pytest.mark.skipif(
    os.getuid() == 0, reason="root bypasses both ownership and mode checks"
)
def test_a_login_owned_by_another_user_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    descriptor = descriptor_for_executable("codex")
    _make_login_tree(tmp_path, descriptor)
    other_uid = os.getuid() + 1
    monkeypatch.setattr(os, "getuid", lambda: other_uid)
    with pytest.raises(AuthProfileError) as caught:
        local_login_presence_for("codex").prove(_parent_env(tmp_path))
    assert str(caught.value) == _absent_message(descriptor)


@pytest.mark.skipif(os.getuid() == 0, reason="root can read a 0o000 file")
def test_proving_never_opens_the_login_artifact(tmp_path: Path) -> None:
    """An unreadable artifact still proves: presence is stat-only, never a read."""

    descriptor = descriptor_for_executable("codex")
    config_dir = _make_login_tree(tmp_path, descriptor)
    artifact = config_dir / descriptor.credential_relative_paths[0]
    artifact.chmod(0o000)
    try:
        with pytest.raises(PermissionError):
            artifact.open("rb").close()
        local_login_presence_for("codex").prove(_parent_env(tmp_path))
        assert stat.S_IMODE(artifact.lstat().st_mode) == 0o000
    finally:
        artifact.chmod(0o600)


def test_config_dir_env_var_relocates_the_login_and_must_be_absolute(
    tmp_path: Path,
) -> None:
    descriptor = descriptor_for_executable("codex")
    relocated = tmp_path / "relocated-codex-home"
    relocated.mkdir()
    for relative in descriptor.credential_relative_paths:
        (relocated / relative).write_bytes(b"opaque")
    presence = local_login_presence_for("codex")
    empty_home = tmp_path / "home"
    empty_home.mkdir()

    relocated_env = _parent_env(empty_home, CODEX_HOME=str(relocated))
    presence.prove(relocated_env)
    assert presence.config_dir(relocated_env) == relocated

    with pytest.raises(AuthProfileError) as caught:
        presence.prove(_parent_env(empty_home, CODEX_HOME="   "))
    assert str(caught.value) == _absent_message(descriptor)

    with pytest.raises(AuthProfileError, match="must be an absolute path"):
        presence.prove(_parent_env(empty_home, CODEX_HOME="relative-codex"))
    with pytest.raises(AuthProfileError, match="must be an absolute path"):
        presence.prove({"PATH": "/usr/bin", "HOME": "relative-home"})
    with pytest.raises(AuthProfileError) as caught:
        presence.prove({"PATH": "/usr/bin"})
    assert str(caught.value) == _absent_message(descriptor)


def test_child_env_and_boundary_paths_expose_only_the_login_directory(
    tmp_path: Path,
) -> None:
    env = _parent_env(tmp_path)

    codex = local_login_presence_for("codex")
    codex_dir = tmp_path / ".codex"
    assert codex.child_env_overrides(env) == {"CODEX_HOME": str(codex_dir)}
    assert codex.boundary_read_paths(env) == (codex_dir,)
    assert codex.boundary_write_paths(env) == (codex_dir,)

    # agy declares no config-dir variable, so HOME is the only way it finds its
    # login; the boundary still grants nothing but the one directory.
    agy = local_login_presence_for("agy")
    assert agy.child_env_overrides(env) == {"HOME": str(tmp_path)}
    assert agy.boundary_read_paths(env) == (tmp_path / ".gemini",)

    assert local_login_presence_for("grok").child_env_overrides(env) == {
        "GROK_DISABLE_AUTOUPDATER": "1",
        "GROK_MEMORY": "0",
        "GROK_HOME": str(tmp_path / ".grok"),
    }
    assert local_login_presence_for("kimi").child_env_overrides(env) == {
        "KIMI_CODE_NO_AUTO_UPDATE": "1",
        "KIMI_CODE_HOME": str(tmp_path / ".kimi-code"),
    }


@pytest.mark.skipif(os.getuid() == 0, reason="root passes the ownership check")
def test_refusals_never_leak_a_host_path_or_the_bytes_on_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Refuse with real login bytes on disk and assert none of it reaches text."""

    allowed = {_absent_message(descriptor) for descriptor in _DESCRIPTORS}
    secret = "token-value-that-must-never-be-quoted"
    homes = {}
    for basename in _BASENAMES:
        home = tmp_path / f"leak-{basename}"
        home.mkdir()
        _make_login_tree(
            home, descriptor_for_executable(basename), contents=secret.encode()
        )
        homes[basename] = home
    other_uid = os.getuid() + 1
    monkeypatch.setattr(os, "getuid", lambda: other_uid)
    for basename, home in homes.items():
        with pytest.raises(AuthProfileError) as caught:
            local_login_presence_for(basename).prove(_parent_env(home))
        message = str(caught.value)
        assert message in allowed
        assert str(tmp_path) not in message
        assert secret not in message
        assert caught.value.__cause__ is None


def test_descriptor_rejects_an_artifact_outside_its_config_directory() -> None:
    with pytest.raises(AuthProfileError, match="outside its own config"):
        HarnessLoginDescriptor(
            executable_basename="codex",
            config_dir_env_var="CODEX_HOME",
            home_relative_config_dir=".codex",
            credential_relative_paths=("../auth.json",),
            login_hint="run 'codex login'",
        )
    with pytest.raises(AuthProfileError, match="no local-login artifact"):
        HarnessLoginDescriptor(
            executable_basename="codex",
            config_dir_env_var="CODEX_HOME",
            home_relative_config_dir=".codex",
            credential_relative_paths=(),
            login_hint="run 'codex login'",
        )
    assert isinstance(local_login_presence_for("codex"), LocalLoginPresence)
