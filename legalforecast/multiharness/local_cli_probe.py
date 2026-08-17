"""Credential-free installed CLI identity and capability probing.

This probe only invokes ``--version`` and ``--help`` in the isolated identity
environment.  It never invokes a model command, resolves auth, reads a keyring,
or uses a provider.  A pin mismatch is reported as observed drift rather than
silently asserted away; callers can then correct a private capability record or
refuse the run before spend.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self, cast

from legalforecast.multiharness.local_cli_environment import (
    identity_probe_environment,
)
from legalforecast.multiharness.local_cli_identity import (
    ExecutableIdentityPin,
    sha256_file,
)
from legalforecast.multiharness.local_cli_manifest import (
    LocalCliAdapterManifest,
    capability_digest_for,
)
from legalforecast.multiharness.validation import (
    MultiHarnessValidationError,
    require_known_fields,
    require_str,
    validate_sha256,
)

LOCAL_CLI_PROBE_SCHEMA_VERSION = (
    # contract-ratchet: allow non-authoritative local CLI probe sidecar
    "legalforecast.multiharness.local_cli_probe.v1"
)
_PROBE_FIELDS = frozenset(
    {
        "schema_version",
        "executable_name",
        "observed_version",
        "observed_sha256",
        "version_output_sha256",
        "help_output_sha256",
        "observed_flags",
        "pin_version_match",
        "pin_digest_match",
        "provider_free",
    }
)
_FLAG_RE = re.compile(r"(?<![A-Za-z0-9_])--[A-Za-z0-9][A-Za-z0-9-]*")
_VERSION_RE = re.compile(r"(?:^|\s)(?:[A-Za-z_-]+\s+)?\d+\.\d+\.\d+(?:[^\n]*)")
_DEFAULT_TIMEOUT_SECONDS = 5.0


class LocalCliProbeError(RuntimeError):
    """An installed CLI could not be observed in the credential-free probe."""


@dataclass(frozen=True, slots=True)
class InstalledCliProbe:
    """Observed binary and help/version evidence, including pin comparison."""

    executable_name: str
    observed_version: str
    observed_sha256: str
    version_output_sha256: str
    help_output_sha256: str
    observed_flags: tuple[str, ...]
    pin_version_match: bool
    pin_digest_match: bool
    provider_free: bool = True

    def __post_init__(self) -> None:
        _require_non_empty(self.executable_name, "executable_name")
        _require_non_empty(self.observed_version, "observed_version")
        _require_raw_sha256(self.observed_sha256, "observed_sha256")
        _require_prefixed_sha256(self.version_output_sha256, "version_output_sha256")
        _require_prefixed_sha256(self.help_output_sha256, "help_output_sha256")
        if not self.provider_free:
            raise LocalCliProbeError("installed CLI probe must be provider-free")

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": LOCAL_CLI_PROBE_SCHEMA_VERSION,
            "executable_name": self.executable_name,
            "observed_version": self.observed_version,
            "observed_sha256": self.observed_sha256,
            "version_output_sha256": self.version_output_sha256,
            "help_output_sha256": self.help_output_sha256,
            "observed_flags": list(self.observed_flags),
            "pin_version_match": self.pin_version_match,
            "pin_digest_match": self.pin_digest_match,
            "provider_free": self.provider_free,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        try:
            require_known_fields(
                record,
                required=_PROBE_FIELDS,
                field_name="local CLI probe",
            )
            raw_flags = record.get("observed_flags")
            if not isinstance(raw_flags, list) or not all(
                type(flag) is str for flag in cast(list[Any], raw_flags)
            ):
                raise LocalCliProbeError("observed_flags must be a string array")
            if type(record.get("pin_version_match")) is not bool:
                raise LocalCliProbeError("pin_version_match must be boolean")
            if type(record.get("pin_digest_match")) is not bool:
                raise LocalCliProbeError("pin_digest_match must be boolean")
            if record.get("provider_free") is not True:
                raise LocalCliProbeError("local CLI probe must be provider-free")
            if require_str(record, "schema_version") != LOCAL_CLI_PROBE_SCHEMA_VERSION:
                raise LocalCliProbeError("unsupported local CLI probe schema")
            return cls(
                executable_name=require_str(record, "executable_name"),
                observed_version=require_str(record, "observed_version"),
                observed_sha256=require_str(record, "observed_sha256"),
                version_output_sha256=require_str(record, "version_output_sha256"),
                help_output_sha256=require_str(record, "help_output_sha256"),
                observed_flags=tuple(cast(list[str], raw_flags)),
                pin_version_match=cast(bool, record["pin_version_match"]),
                pin_digest_match=cast(bool, record["pin_digest_match"]),
                provider_free=True,
            )
        except (MultiHarnessValidationError, TypeError, ValueError) as exc:
            raise LocalCliProbeError(str(exc)) from exc


def probe_installed_cli(
    pin: ExecutableIdentityPin,
    *,
    version_args: Sequence[str] = ("--version",),
    help_args: Sequence[str] = ("--help",),
    scratch_root: Path,
    parent_env: Mapping[str, str] | None = None,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
) -> InstalledCliProbe:
    """Probe a PATH-installed executable without provider/auth resolution."""

    if timeout_seconds <= 0:
        raise LocalCliProbeError("probe timeout must be positive")
    parent = os.environ if parent_env is None else parent_env
    search_path = parent.get("PATH", "/usr/bin")
    located = shutil.which(pin.basename, path=search_path)
    if located is None:
        raise LocalCliProbeError(f"installed executable {pin.basename!r} was not found")
    executable = Path(located)
    if executable.is_symlink():
        resolved = executable.resolve()
    else:
        resolved = executable
    if not resolved.is_file():
        raise LocalCliProbeError("installed executable is not a regular file")
    observed_digest = sha256_file(resolved)
    try:
        probe_env = identity_probe_environment(scratch_root, parent)
        version_output = _run_probe(
            resolved,
            version_args,
            environment=probe_env,
            timeout_seconds=timeout_seconds,
        )
        help_output = _run_probe(
            resolved,
            help_args,
            environment=probe_env,
            timeout_seconds=timeout_seconds,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise LocalCliProbeError("credential-free CLI identity probe failed") from exc
    version = _extract_version(version_output)
    flags = tuple(sorted(set(_FLAG_RE.findall(help_output))))
    return InstalledCliProbe(
        executable_name=pin.basename,
        observed_version=version,
        observed_sha256=observed_digest,
        version_output_sha256=_prefixed_digest(version_output),
        help_output_sha256=_prefixed_digest(help_output),
        observed_flags=flags,
        pin_version_match=version == pin.version,
        pin_digest_match=observed_digest == pin.sha256,
    )


def probe_manifest_executable(
    manifest_path: Path,
    *,
    scratch_root: Path,
    parent_env: Mapping[str, str] | None = None,
    version_args: Sequence[str] = ("--version",),
    help_args: Sequence[str] = ("--help",),
) -> InstalledCliProbe:
    """Load an adapter capability record and probe its declared executable."""

    import json

    try:
        record = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LocalCliProbeError("local CLI capability record is unreadable") from exc
    if not isinstance(record, Mapping):
        raise LocalCliProbeError("local CLI capability record must be an object")
    try:
        manifest = LocalCliAdapterManifest.from_record(cast(Mapping[str, Any], record))
    except (MultiHarnessValidationError, ValueError) as exc:
        raise LocalCliProbeError("local CLI capability record is invalid") from exc
    executable = manifest.executable
    pin = ExecutableIdentityPin(
        basename=executable.basename,
        version=executable.version,
        sha256=executable.sha256,
        distribution_kind=executable.distribution_kind,
    )
    return probe_installed_cli(
        pin,
        version_args=version_args,
        help_args=help_args,
        scratch_root=scratch_root,
        parent_env=parent_env,
    )


def corrected_capability_record(
    record: Mapping[str, Any],
    observed: InstalledCliProbe,
) -> dict[str, object]:
    """Return a capability record corrected from observed identity evidence.

    Only executable version and digest are corrected.  Capabilities are never
    inferred from a pin mismatch or asserted from a version string.  The
    caller may persist this returned record in its private run archive after
    reviewing the observed help flags.
    """

    corrected = dict(record)
    raw_executable = record.get("executable")
    if not isinstance(raw_executable, Mapping):
        raise LocalCliProbeError("capability record executable must be an object")
    executable = dict(cast(Mapping[str, object], raw_executable))
    basename = executable.get("basename")
    if basename != observed.executable_name:
        raise LocalCliProbeError("observed executable basename does not match record")
    executable["version"] = observed.observed_version
    executable["sha256"] = observed.observed_sha256
    corrected["executable"] = executable
    if "capability_digest" in corrected:
        corrected["capability_digest"] = capability_digest_for(
            cast(Mapping[str, Any], corrected)
        )
    # Re-parse to ensure correcting identity did not loosen the closed record.
    try:
        LocalCliAdapterManifest.from_record(cast(Mapping[str, Any], corrected))
    except (MultiHarnessValidationError, ValueError) as exc:
        raise LocalCliProbeError("corrected capability record is invalid") from exc
    return corrected


def _run_probe(
    executable: Path,
    args: Sequence[str],
    *,
    environment: Mapping[str, str],
    timeout_seconds: float,
) -> str:
    try:
        completed = subprocess.run(
            (str(executable), *args),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            cwd=executable.parent,
            env=dict(environment),
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise LocalCliProbeError("identity probe process failed") from exc
    if completed.returncode != 0:
        raise LocalCliProbeError("identity probe returned a nonzero status")
    try:
        return completed.stdout.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LocalCliProbeError("identity probe output is not UTF-8") from exc


def _extract_version(output: str) -> str:
    for line in output.splitlines():
        candidate = line.strip()
        if candidate and _VERSION_RE.search(candidate):
            return candidate
    raise LocalCliProbeError("identity probe did not report a semantic version")


def _prefixed_digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _require_raw_sha256(value: str, field_name: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise LocalCliProbeError(f"{field_name} must be a lowercase SHA-256 digest")


def _require_prefixed_sha256(value: str, field_name: str) -> None:
    try:
        validate_sha256(value, field_name)
    except MultiHarnessValidationError as exc:
        raise LocalCliProbeError(str(exc)) from exc


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise LocalCliProbeError(f"{field_name} must be non-empty")
