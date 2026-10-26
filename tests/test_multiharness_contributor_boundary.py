"""Contributor-grade Landlock boundary identity and write-deny proof."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from legalforecast.multiharness import contributor_boundary
from legalforecast.multiharness._landlock_exec import path_beneath_struct_size
from legalforecast.multiharness.contributor_boundary import (
    CONTRIBUTOR_NATIVE_BOUNDARY,
    HOSTILE_DENIED,
    HOSTILE_IN_SCOPE,
    HOSTILE_QUARANTINED,
    HOSTILE_REFUSED,
    LINUX_LANDLOCK_FS_SCOPE,
    ContributorBoundaryError,
    classify_hostile_probe,
    contributor_boundary_plan,
    preflight_contributor_boundary,
    require_filesystem_scope,
    wrap_argv_for_contributor_boundary,
)

_FAKE_CLI = Path(__file__).resolve().parent / "fixtures" / "local_cli_fake_cli.py"


def test_path_beneath_matches_packed_kernel_layout() -> None:
    assert path_beneath_struct_size() == 12


def test_preflight_and_plan_are_path_free() -> None:
    abi = preflight_contributor_boundary()
    assert abi >= 1
    record = contributor_boundary_plan(
        host_process_containment="posix_process_group.v1"
    ).to_public_record()
    assert record["policy_id"] == CONTRIBUTOR_NATIVE_BOUNDARY
    assert record["filesystem_scope"] == LINUX_LANDLOCK_FS_SCOPE
    assert record["isolated_environment"] is True
    assert record["transcript_redaction"] is True
    serialized = json.dumps(record)
    assert str(Path.home()) not in serialized
    assert "scratch" not in serialized


def test_unknown_filesystem_scope_is_refused() -> None:
    with pytest.raises(ContributorBoundaryError, match=r"linux_landlock_fs\.v1"):
        require_filesystem_scope(None)
    with pytest.raises(ContributorBoundaryError, match=r"linux_landlock_fs\.v1"):
        require_filesystem_scope("bubblewrap")
    assert require_filesystem_scope(LINUX_LANDLOCK_FS_SCOPE) == LINUX_LANDLOCK_FS_SCOPE


def test_classify_hostile_probe_is_closed() -> None:
    assert classify_hostile_probe(in_scope=False, denied=True, tampered=False) == (
        HOSTILE_DENIED
    )
    assert classify_hostile_probe(in_scope=True, denied=False, tampered=True) == (
        HOSTILE_QUARANTINED
    )
    assert classify_hostile_probe(in_scope=True, denied=False, tampered=False) == (
        HOSTILE_IN_SCOPE
    )
    assert classify_hostile_probe(in_scope=False, denied=False, tampered=False) == (
        HOSTILE_REFUSED
    )


def test_landlock_wrapper_denies_out_of_scope_write(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / "pwned.txt"
    argv = (
        sys.executable,
        str(_FAKE_CLI),
        "--mode",
        "write-probe",
        "--path",
        str(target),
        "--payload",
        "pwned",
    )
    wrapped, identity = wrap_argv_for_contributor_boundary(
        argv,
        scratch_root=scratch,
    )
    completed = subprocess.run(
        wrapped,
        cwd=scratch,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert identity["policy_id"] == CONTRIBUTOR_NATIVE_BOUNDARY
    assert identity["filesystem_scope"] == LINUX_LANDLOCK_FS_SCOPE
    assert "landlock_abi" in identity
    assert not target.exists()
    assert completed.returncode != 0
    record = json.loads(completed.stdout.decode("utf-8") or "{}")
    assert record.get("ok") is False
    assert (
        classify_hostile_probe(
            in_scope=False,
            denied=not target.exists(),
            tampered=False,
        )
        == HOSTILE_DENIED
    )


def test_landlock_wrapper_allows_in_scope_scratch_write(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    target = scratch / "in-scope.txt"
    argv = (
        sys.executable,
        str(_FAKE_CLI),
        "--mode",
        "write-probe",
        "--path",
        str(target),
        "--payload",
        "ok",
    )
    wrapped, _identity = wrap_argv_for_contributor_boundary(
        argv,
        scratch_root=scratch,
    )
    completed = subprocess.run(
        wrapped,
        cwd=scratch,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert completed.returncode == 0
    assert target.read_text(encoding="utf-8") == "ok"
    assert (
        classify_hostile_probe(
            in_scope=True,
            denied=False,
            tampered=False,
        )
        == HOSTILE_IN_SCOPE
    )


def test_system_resolver_symlink_target_readable_without_sibling_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    resolver_directory = tmp_path / "system-resolver"
    resolver_directory.mkdir()
    target = resolver_directory / "stub-resolv.conf"
    target.write_text("nameserver 192.0.2.1\n", encoding="utf-8")
    private = resolver_directory / "private.txt"
    private.write_text("synthetic private data", encoding="utf-8")
    resolver_link = tmp_path / "resolv.conf"
    resolver_link.symlink_to(target)
    monkeypatch.setattr(
        contributor_boundary,
        "_SYSTEM_RESOLVER_FILES",
        (str(resolver_link),),
    )
    for path, expected in ((resolver_link, True), (private, False)):
        argv = (
            sys.executable,
            str(_FAKE_CLI),
            "--mode",
            "read-probe",
            "--path",
            str(path),
        )
        wrapped, _identity = wrap_argv_for_contributor_boundary(
            argv, scratch_root=scratch
        )
        completed = subprocess.run(
            wrapped, cwd=scratch, capture_output=True, timeout=10, check=False
        )
        record = json.loads(completed.stdout)
        assert record["ok"] is expected, completed.stderr.decode()


def test_landlock_rejects_symlink_read_grant_at_admission(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    target = tmp_path / "target"
    target.mkdir()
    planted = tmp_path / "planted"
    planted.symlink_to(target, target_is_directory=True)

    with pytest.raises(ContributorBoundaryError, match="must not be a symlink"):
        wrap_argv_for_contributor_boundary(
            (sys.executable, "-c", "raise SystemExit(0)"),
            scratch_root=scratch,
            extra_read_paths=(planted,),
        )


def test_landlock_rejects_read_grant_swapped_to_symlink_before_materialization(
    tmp_path: Path,
) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    granted = tmp_path / "codex-daemon-fixture"
    granted.mkdir(mode=0o700)
    target = tmp_path / "target"
    target.mkdir()
    wrapped, _identity = wrap_argv_for_contributor_boundary(
        (sys.executable, "-c", "raise SystemExit(0)"),
        scratch_root=scratch,
        extra_read_paths=(granted,),
    )
    granted.rmdir()
    granted.symlink_to(target, target_is_directory=True)

    completed = subprocess.run(
        wrapped,
        cwd=scratch,
        capture_output=True,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 125
