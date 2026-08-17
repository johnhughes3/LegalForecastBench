"""Supported installer for the pinned ``harvey-lab-eval`` entrypoint.

A Tier-0 executable spec names ``evaluator_command`` and pins
``evaluator_wrapper_sha256``; the runner resolves that basename on PATH and
refuses when the installed bytes do not match.  Until this module existed there
was no supported way to put those bytes on PATH, so the digest could not be
minted and the spec could not be completed -- enforcement without issuance.

Installation is a byte-identical copy of the committed script.  That is the
whole point: the digest an operator can compute from the repository before
installing anything is the digest the runner will verify afterwards.  Nothing
is templated, stamped, or rewritten at install time.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path

from legalforecast.multiharness.local_cli_identity import (
    ExecutableIdentityPin,
    sha256_file,
)
from legalforecast.multiharness.local_cli_probe import (
    InstalledCliProbe,
    LocalCliProbeError,
    probe_installed_cli,
)

EVALUATOR_WRAPPER_INSTALL_SCHEMA_VERSION = (
    # contract-ratchet: allow non-authoritative evaluator wrapper install record
    "legalforecast.multiharness.evaluator_wrapper_install.v1"
)
HARVEY_LAB_EVAL_WRAPPER_NAME = "harvey-lab-eval"
HARVEY_LAB_EVAL_WRAPPER_SOURCE = (
    Path(__file__).resolve().parents[2] / "scripts" / HARVEY_LAB_EVAL_WRAPPER_NAME
)
_VERSION_ASSIGNMENT = re.compile(
    r'^HARVEY_LAB_EVAL_WRAPPER_VERSION\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"$',
    re.MULTILINE,
)
_INSTALLED_MODE = 0o755


class EvaluatorWrapperInstallError(ValueError):
    """The pinned evaluator wrapper could not be installed or verified."""


@dataclass(frozen=True, slots=True)
class InstalledEvaluatorWrapper:
    """Where the pinned wrapper landed and what the probe observed there."""

    install_path: Path
    wrapper_sha256: str
    wrapper_version: str
    probe: InstalledCliProbe

    def to_record(self) -> dict[str, object]:
        """Return a public-safe install record.

        ``install_path`` is deliberately reduced to its basename: this record
        is committed alongside freeze material in a public repository, and an
        absolute install path is machine-specific operator detail.
        """

        return {
            "schema_version": EVALUATOR_WRAPPER_INSTALL_SCHEMA_VERSION,
            "executable_name": self.install_path.name,
            "wrapper_sha256": self.wrapper_sha256,
            "wrapper_version": self.wrapper_version,
            "probe": self.probe.to_record(),
        }


def wrapper_source_version() -> str:
    """Return the version constant declared inside the committed wrapper."""

    text = _read_source()
    match = _VERSION_ASSIGNMENT.search(text)
    if match is None:
        raise EvaluatorWrapperInstallError(
            "committed evaluator wrapper does not declare a pinned version"
        )
    return match.group(1)


def wrapper_source_sha256() -> str:
    """Return the prefixed digest of the committed wrapper bytes."""

    try:
        return "sha256:" + sha256_file(HARVEY_LAB_EVAL_WRAPPER_SOURCE)
    except OSError as exc:
        raise EvaluatorWrapperInstallError(
            "committed evaluator wrapper is unreadable"
        ) from exc


def wrapper_identity_pin() -> ExecutableIdentityPin:
    """Return the pin the capability probe compares the installation against."""

    version = wrapper_source_version()
    return ExecutableIdentityPin(
        basename=HARVEY_LAB_EVAL_WRAPPER_NAME,
        version=f"{HARVEY_LAB_EVAL_WRAPPER_NAME} {version}",
        sha256=wrapper_source_sha256().removeprefix("sha256:"),
    )


def install_evaluator_wrapper(
    bin_dir: Path,
    *,
    scratch_root: Path,
    overwrite: bool = False,
) -> InstalledEvaluatorWrapper:
    """Install the committed wrapper into ``bin_dir`` and probe the result.

    ``scratch_root`` is the fresh directory the credential-free capability
    probe uses as an isolated HOME/XDG root.  The probe runs against the
    installed path only, so a caller cannot pass the verification by leaving a
    different ``harvey-lab-eval`` earlier on PATH.
    """

    source = HARVEY_LAB_EVAL_WRAPPER_SOURCE
    if not source.is_file() or source.is_symlink():
        raise EvaluatorWrapperInstallError(
            "committed evaluator wrapper is not a regular file"
        )
    target_dir = _require_install_dir(bin_dir)
    target = target_dir / HARVEY_LAB_EVAL_WRAPPER_NAME
    if target.is_symlink():
        raise EvaluatorWrapperInstallError("install target must not be a symlink")
    if target.exists() and not overwrite:
        raise EvaluatorWrapperInstallError(
            "install target already exists; pass overwrite to replace it"
        )
    expected = wrapper_source_sha256()
    version = wrapper_source_version()
    try:
        shutil.copyfile(source, target)
        os.chmod(target, _INSTALLED_MODE)
    except OSError as exc:
        raise EvaluatorWrapperInstallError(
            "evaluator wrapper could not be written to the install directory"
        ) from exc
    observed = "sha256:" + sha256_file(target)
    if observed != expected:
        raise EvaluatorWrapperInstallError(
            "installed evaluator wrapper does not match the committed bytes"
        )
    mode = target.stat().st_mode
    if not mode & stat.S_IXUSR:
        raise EvaluatorWrapperInstallError(
            "installed evaluator wrapper is not executable"
        )
    probe = _probe_installed(target_dir, scratch_root=scratch_root)
    if not probe.pin_digest_match:
        raise EvaluatorWrapperInstallError(
            "capability probe resolved a different harvey-lab-eval on PATH"
        )
    if not probe.pin_version_match:
        raise EvaluatorWrapperInstallError(
            "installed evaluator wrapper reported an unexpected version"
        )
    return InstalledEvaluatorWrapper(
        install_path=target,
        wrapper_sha256=expected,
        wrapper_version=version,
        probe=probe,
    )


def _probe_installed(
    target_dir: Path,
    *,
    scratch_root: Path,
) -> InstalledCliProbe:
    # The install directory comes first so an unrelated `harvey-lab-eval`
    # earlier on the caller's PATH cannot satisfy the probe; the platform
    # default path follows it because the wrapper's `/usr/bin/env python3`
    # shebang has to resolve an interpreter, exactly as it must inside the
    # contained Tier-0 run. The digest check is what proves which bytes ran.
    probe_env = {"PATH": os.pathsep.join((str(target_dir), os.defpath))}
    try:
        return probe_installed_cli(
            wrapper_identity_pin(),
            scratch_root=scratch_root,
            parent_env=probe_env,
        )
    except LocalCliProbeError as exc:
        raise EvaluatorWrapperInstallError(
            "installed evaluator wrapper failed the credential-free probe"
        ) from exc


def _require_install_dir(bin_dir: Path) -> Path:
    if bin_dir.is_symlink():
        raise EvaluatorWrapperInstallError("install directory must not be a symlink")
    if not bin_dir.is_dir():
        raise EvaluatorWrapperInstallError(
            "install directory must exist and be a real directory"
        )
    return bin_dir.resolve()


def _read_source() -> str:
    try:
        return HARVEY_LAB_EVAL_WRAPPER_SOURCE.read_text(encoding="utf-8")
    except OSError as exc:
        raise EvaluatorWrapperInstallError(
            "committed evaluator wrapper is unreadable"
        ) from exc
