"""Codex arg0 aliases must point directly to the explicitly pinned executable."""

from __future__ import annotations

import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from legalforecast.multiharness.auth_profiles import AuthProfileError
from legalforecast.multiharness.harvey_lab_subscription_operator import (
    build_community_subscription_runtime,
)
from legalforecast.multiharness.local_cli_identity import (
    ExecutableIdentityPin,
    sha256_file,
)
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService
from legalforecast.multiharness.native_cli_subscription import (
    NativeCliSubscriptionPresence,
    validate_auth_only_config_root,
)

from test_codex_lab_subscription_operator import _request
from test_native_cli_subscription import _auth_root

_HELPERS = ("applypatch", "apply_patch", "codex-linux-sandbox")


def _codex_state(tmp_path: Path) -> tuple[Path, Path, ExecutableIdentityPin]:
    binary = tmp_path / "bin" / "codex"
    binary.parent.mkdir()
    binary.write_text("#!/bin/sh\nexit 99\n")
    binary.chmod(0o700)
    pin = ExecutableIdentityPin(
        basename="codex", version="0.164.0", sha256=sha256_file(binary)
    )
    root = _auth_root(tmp_path, "role", "auth.json")
    helper = root / "tmp" / "arg0-linux" / "codex-arg0Abc123"
    helper.mkdir(mode=0o775, parents=True)
    (helper / ".lock").touch(mode=0o664)
    for name in _HELPERS:
        (helper / name).symlink_to(binary)
    return root, helper, pin


def _validate(root: Path, binary_parent: Path, pin: ExecutableIdentityPin) -> Path:
    return validate_auth_only_config_root(
        "codex",
        root,
        role="solver",
        codex_pin=pin,
        codex_search_path=str(binary_parent),
    )


def test_codex_retains_only_helpers_for_explicit_pinned_binary(tmp_path: Path) -> None:
    root, _helper, pin = _codex_state(tmp_path)
    assert _validate(root, tmp_path / "bin", pin) == root
    assert _validate(root, tmp_path / "bin", pin) == root


@pytest.mark.parametrize(
    "tamper",
    ["target", "digest", "extra", "lock-link", "helper-file", "directory-link"],
)
def test_codex_helper_state_rejects_unpinned_or_unexpected_paths(
    tmp_path: Path, tamper: str
) -> None:
    root, helper, pin = _codex_state(tmp_path)
    if tamper == "target":
        (helper / "apply_patch").unlink()
        (helper / "apply_patch").symlink_to(tmp_path / "outside")
    elif tamper == "digest":
        (tmp_path / "bin" / "codex").write_text("changed binary")
    elif tamper == "extra":
        (helper / "settings.json").write_text("{}")
    elif tamper == "lock-link":
        (helper / ".lock").unlink()
        (helper / ".lock").symlink_to(tmp_path / "outside")
    elif tamper == "helper-file":
        (helper / "apply_patch").unlink()
        (helper / "apply_patch").touch()
    else:
        helper.rename(helper.with_name("outside"))
        helper.symlink_to(helper.with_name("outside"), target_is_directory=True)
    with pytest.raises(AuthProfileError):
        _validate(root, tmp_path / "bin", pin)


def test_codex_helpers_require_explicit_identity(tmp_path: Path) -> None:
    root, _helper, _pin = _codex_state(tmp_path)
    with pytest.raises(AuthProfileError):
        validate_auth_only_config_root("codex", root, role="solver")


def test_codex_presence_revalidates_helpers_with_same_pinned_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _helper, pin = _codex_state(tmp_path)
    monkeypatch.setattr(
        "legalforecast.multiharness.native_cli_subscription.wrap_argv_for_contributor_boundary",
        lambda argv, **_kwargs: (argv, {}),
    )
    monkeypatch.setattr(
        "legalforecast.multiharness.native_cli_subscription.subprocess.run",
        lambda argv, **_kwargs: subprocess.CompletedProcess(
            argv, 0, b"", b"Logged in using ChatGPT\n"
        ),
    )
    presence = NativeCliSubscriptionPresence(
        "codex", config_root=root, role="solver", executable_pin=pin
    )
    for _attempt in range(2):
        access = presence.prove({"PATH": str(tmp_path / "bin")})
        assert access.environment == (("CODEX_HOME", str(root)),)


def test_operator_threads_pin_to_initial_helper_validation(tmp_path: Path) -> None:
    root, _helper, pin = _codex_state(tmp_path)
    operator_root = tmp_path / "operator"
    operator_root.mkdir()
    request = replace(
        _request(operator_root),
        solver_config_dir=root,
        evaluator_bin_dir=tmp_path / "bin",
        codex_version=pin.version,
        codex_sha256=pin.sha256,
    )
    runtime = build_community_subscription_runtime(request)
    service = runtime.adapter.execution_service
    assert isinstance(service, LocalCliExecutionService)
    assert service.executable_pin is not None
    assert service.executable_pin.sha256 == pin.sha256
