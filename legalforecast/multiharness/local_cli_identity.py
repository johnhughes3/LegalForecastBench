"""Fail-closed executable identity and framing for the local CLI runtime.

The service binds each launch to the exact bytes named by the manifest pin
(basename + digest + version). A swapped or drifted binary is a refusal, never
a silent run. The launch path keeps the pin basename, including Homebrew or
npm shims; hashing follows that path so the digest is the bytes ``exec`` runs.
Host paths stay off public receipts; error text carries basename and digests
only, including when the filesystem itself refuses (a raw ``OSError`` message
would embed the host path, so bind-time ``OSError`` becomes a path-free
``LocalCliIdentityError``; GitHub #724).

``bind_executable_identity`` is the full bind: digest plus the optional
self-attestation probe, which needs an environment and launches a child.
``verify_executable_digest`` is the credential-free half: it takes a bare
``PATH`` string, never an environment mapping, and can never spawn. Callers
re-checking the digest immediately before spawn use the digest-only helper so
projected credentials are not threaded into a helper that can also launch a
probe (GitHub #722).
"""

from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from legalforecast.multiharness.auth_profiles import AuthProfileError
from legalforecast.multiharness.local_cli_environment import identity_probe_environment
from legalforecast.multiharness.validation import validate_sha256

LOCAL_CLI_EXECUTABLE_PIN_SCHEMA_VERSION = (
    # contract-ratchet: allow non-persisted local CLI executable pin
    "legalforecast.multiharness.local_cli_executable_pin.v1"
)
LOCAL_CLI_IDENTITY_PROBE_SCHEMA_VERSION = (
    # contract-ratchet: allow non-persisted local CLI identity probe
    "legalforecast.multiharness.local_cli_identity_probe.v1"
)
LOCAL_CLI_DISTRIBUTION_KINDS = frozenset(
    {
        "fixture",
        "homebrew-cask",
        "sdk-bundled",
        "standalone-cli",
    }
)
_IDENTITY_PROBE_TIMEOUT_SECONDS = 5.0
_HASH_CHUNK_BYTES = 1_048_576


class LocalCliIdentityError(RuntimeError):
    """Raised when executable identity or framing cannot be bound."""

    def __init__(self, message: str, *, failure_class: str) -> None:
        super().__init__(message)
        self.failure_class = failure_class


@dataclass(frozen=True, slots=True)
class ExecutableIdentityPin:
    """Pinned executable identity. Public fields never include host paths."""

    basename: str
    version: str
    sha256: str
    distribution_kind: str = "fixture"
    required_flags: tuple[str, ...] = ()
    allowed_events: tuple[str, ...] = ()
    allowed_models: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.basename.strip() or "/" in self.basename or "\\" in self.basename:
            raise LocalCliIdentityError(
                "executable basename must be a pathless command name",
                failure_class="basename_mismatch",
            )
        if not self.version.strip():
            raise LocalCliIdentityError(
                "executable version must not be empty",
                failure_class="version_mismatch",
            )
        validate_sha256(self.sha256, "executable.sha256", allow_prefix=False)
        if self.distribution_kind not in LOCAL_CLI_DISTRIBUTION_KINDS:
            raise LocalCliIdentityError(
                "executable distribution_kind is not recognized",
                failure_class="unknown_schema",
            )

    def to_record(self) -> dict[str, object]:
        """Return the path-free pin recorded on specs and receipts."""

        return {
            "schema_version": LOCAL_CLI_EXECUTABLE_PIN_SCHEMA_VERSION,
            "basename": self.basename,
            "version": self.version,
            "sha256": self.sha256,
            "distribution_kind": self.distribution_kind,
            "required_flags": list(self.required_flags),
            "allowed_events": list(self.allowed_events),
            "allowed_models": list(self.allowed_models),
        }


LocalCliExecutablePin = ExecutableIdentityPin


@dataclass(frozen=True, slots=True)
class ObservedExecutableIdentity:
    """Resolved identity after a successful digest (and optional probe) bind."""

    basename: str
    version: str
    sha256: str
    distribution_kind: str
    resolved_argv: tuple[str, ...]


BoundExecutableIdentity = ObservedExecutableIdentity


# contract-ratchet: allow non-persisted executable digest for identity bind
def sha256_file(path: Path) -> str:
    """Return the unprefixed SHA-256 of a regular file's bytes."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(_HASH_CHUNK_BYTES)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def executable_pin_for(
    path: Path,
    *,
    version: str = "0.1.0",
    distribution_kind: str = "fixture",
    required_flags: tuple[str, ...] = (),
    allowed_events: tuple[str, ...] = (),
    allowed_models: tuple[str, ...] = (),
) -> ExecutableIdentityPin:
    """Hash ``path`` and return a pin bound to its basename."""

    return ExecutableIdentityPin(
        basename=path.name,
        version=version,
        sha256=sha256_file(path),
        distribution_kind=distribution_kind,
        required_flags=required_flags,
        allowed_events=allowed_events,
        allowed_models=allowed_models,
    )


pin_executable_file = executable_pin_for


def verify_executable_digest(
    pin: ExecutableIdentityPin,
    argv: Sequence[str],
    *,
    search_path: str,
) -> ObservedExecutableIdentity:
    """Resolve the launch path from argv and re-hash it, with no environment.

    This is the credential-free half of :func:`bind_executable_identity`. It
    takes a bare ``PATH`` string rather than an environment mapping and never
    launches a process, so a caller re-checking the digest immediately before
    ``Popen`` cannot leak projected credentials into a helper that can also
    spawn an identity probe (GitHub #722).

    Filesystem races -- the file deleted, replaced by a directory, or made
    unreadable between resolution and hashing -- raise a path-free
    ``LocalCliIdentityError`` instead of an ``OSError`` whose message embeds
    the host path (GitHub #724).
    """

    try:
        identity_path = _resolve_identity_path(
            argv,
            pin.basename,
            search_path=search_path,
        )
        digest = sha256_file(identity_path)
    except OSError as exc:
        # Never interpolate str(exc): OSError text embeds the host path.
        raise LocalCliIdentityError(
            "executable bytes could not be read",
            failure_class="unreadable_executable",
        ) from exc
    if identity_path.name != pin.basename:
        raise LocalCliIdentityError(
            "executable basename mismatch",
            failure_class="basename_mismatch",
        )
    if digest != pin.sha256:
        raise LocalCliIdentityError(
            "executable digest mismatch",
            failure_class="digest_mismatch",
        )
    return ObservedExecutableIdentity(
        basename=pin.basename,
        version=pin.version,
        sha256=digest,
        distribution_kind=pin.distribution_kind,
        resolved_argv=_argv_with_identity(argv, pin.basename, identity_path),
    )


def bind_executable_identity(
    pin: ExecutableIdentityPin,
    argv: Sequence[str],
    *,
    version_probe_args: Sequence[str] = (),
    required_capabilities: Sequence[str] = (),
    scratch_root: Path | None = None,
    parent_env: Mapping[str, str] | None = None,
    requested_model: str | None = None,
    probe: bool = True,
) -> ObservedExecutableIdentity:
    """Resolve the identity file from argv, hash it, and refuse on mismatch.

    The digest half is :func:`verify_executable_digest`; this wrapper adds the
    pin's capability framing and the optional identity probe, which needs an
    environment because it launches a child process.
    """

    search_path = (parent_env or os.environ).get("PATH", "/usr/bin")
    observed = verify_executable_digest(pin, argv, search_path=search_path)
    resolved_argv = observed.resolved_argv
    needs_probe = bool(
        version_probe_args
        or required_capabilities
        or pin.required_flags
        or pin.allowed_events
        or requested_model
    )
    if requested_model and pin.allowed_models:
        if requested_model not in pin.allowed_models:
            raise LocalCliIdentityError(
                "requested model drift",
                failure_class="model_drift",
            )
    if not probe or not needs_probe:
        if needs_probe and not version_probe_args:
            raise LocalCliIdentityError(
                "identity probe required for capability framing",
                failure_class="probe_framing",
            )
        return observed
    if not version_probe_args:
        raise LocalCliIdentityError(
            "identity probe required for capability framing",
            failure_class="probe_framing",
        )
    if scratch_root is None:
        raise LocalCliIdentityError(
            "identity probe requires scratch isolation",
            failure_class="probe_framing",
        )
    probe_parent = os.environ if parent_env is None else parent_env
    try:
        probe_env = identity_probe_environment(scratch_root, probe_parent)
    except AuthProfileError as exc:
        raise LocalCliIdentityError(
            str(exc),
            failure_class="probe_framing",
        ) from exc
    prefix = _launch_prefix(resolved_argv, pin.basename)
    probe_record = _run_identity_probe(
        (*prefix, *version_probe_args),
        environment=probe_env,
        cwd=scratch_root,
    )
    _check_probe(
        probe_record,
        pin,
        required_capabilities=tuple(required_capabilities),
        requested_model=requested_model,
    )
    return observed


def _argv_with_identity(
    argv: Sequence[str],
    basename: str,
    identity_path: Path,
) -> tuple[str, ...]:
    """Replace the identity token with the hashed launch path.

    Only the first argv token whose basename matches the pin is the
    executable. Later tokens with the same name are extra args.
    """

    rewritten = list(argv)
    identity = str(identity_path)
    for index, token in enumerate(rewritten):
        if Path(token).name == basename:
            rewritten[index] = identity
            return tuple(rewritten)
    raise LocalCliIdentityError(
        "executable basename mismatch",
        failure_class="basename_mismatch",
    )


def _launch_prefix(argv: Sequence[str], basename: str) -> tuple[str, ...]:
    for index, token in enumerate(argv):
        if Path(token).name == basename:
            return tuple(argv[: index + 1])
    raise LocalCliIdentityError(
        "executable basename mismatch",
        failure_class="basename_mismatch",
    )


def _resolve_identity_path(
    argv: Sequence[str],
    basename: str,
    *,
    search_path: str,
) -> Path:
    """Return the named launch path without following a final symlink.

    Homebrew and npm shims keep the pin basename (``claude``) while the
    hashed bytes live at a different target name (``cli.js``). ``open``
    follows the symlink when hashing, so the digest still binds the
    bytes that ``exec`` will run.
    """

    for token in argv:
        candidate = Path(token)
        if candidate.name != basename:
            continue
        if candidate.is_absolute():
            if candidate.is_file():
                return candidate
            raise LocalCliIdentityError(
                "executable basename mismatch",
                failure_class="basename_mismatch",
            )
        if "/" in token or "\\" in token:
            raise LocalCliIdentityError(
                "executable path must be absolute",
                failure_class="basename_mismatch",
            )
        located = _which(token, search_path)
        if located is None or not located.is_file():
            raise LocalCliIdentityError(
                "executable basename mismatch",
                failure_class="basename_mismatch",
            )
        return located
    raise LocalCliIdentityError(
        "executable basename mismatch",
        failure_class="basename_mismatch",
    )


def _which(name: str, search_path: str) -> Path | None:
    for directory in search_path.split(os.pathsep):
        if not directory:
            continue
        candidate = Path(directory) / name
        if not candidate.is_absolute():
            candidate = candidate.absolute()
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


def _run_identity_probe(
    argv: Sequence[str],
    *,
    environment: Mapping[str, str],
    cwd: Path,
    timeout_seconds: float = _IDENTITY_PROBE_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    try:
        process = subprocess.Popen(
            tuple(argv),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=dict(environment),
            start_new_session=True,
        )
    except OSError as exc:
        # FileNotFoundError/PermissionError text embeds the host path.
        raise LocalCliIdentityError(
            "identity probe could not be launched",
            failure_class="probe_framing",
        ) from exc
    try:
        stdout, _stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        _kill_process_group(process)
        try:
            process.communicate(timeout=1)
        except (subprocess.TimeoutExpired, ValueError):
            # Pipes may already be closed after SIGKILL; drain is best-effort.
            pass
        raise LocalCliIdentityError(
            "identity probe timed out",
            failure_class="probe_framing",
        ) from None
    except OSError as exc:
        _kill_process_group(process)
        raise LocalCliIdentityError(
            "identity probe framing",
            failure_class="probe_framing",
        ) from exc
    if process.returncode != 0:
        raise LocalCliIdentityError(
            "identity probe framing",
            failure_class="probe_framing",
        )
    return _parse_identity_probe(stdout)


def _parse_identity_probe(stdout: bytes) -> dict[str, Any]:
    try:
        decoded = json.loads(stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LocalCliIdentityError(
            "identity probe framing",
            failure_class="probe_framing",
        ) from exc
    if not isinstance(decoded, dict):
        raise LocalCliIdentityError(
            "identity probe framing",
            failure_class="probe_framing",
        )
    record = cast(dict[str, Any], decoded)
    schema = record.get("schema_version")
    if schema != LOCAL_CLI_IDENTITY_PROBE_SCHEMA_VERSION:
        raise LocalCliIdentityError(
            "unknown identity schema",
            failure_class="unknown_schema",
        )
    return record


def _check_probe(
    record: Mapping[str, Any],
    pin: ExecutableIdentityPin,
    *,
    required_capabilities: Sequence[str],
    requested_model: str | None,
) -> None:
    reported_version = _optional_str(record, "version")
    if reported_version is None or reported_version != pin.version:
        raise LocalCliIdentityError(
            "executable version mismatch",
            failure_class="version_mismatch",
        )
    reported_basename = _optional_str(record, "basename")
    if reported_basename is not None and reported_basename != pin.basename:
        raise LocalCliIdentityError(
            "executable basename mismatch",
            failure_class="basename_mismatch",
        )
    flags = _optional_str_tuple(record, "flags")
    missing_flags = [flag for flag in pin.required_flags if flag not in flags]
    if missing_flags:
        raise LocalCliIdentityError(
            "required flag missing",
            failure_class="missing_flag",
        )
    capabilities = _optional_str_tuple(record, "capabilities")
    missing_caps = [name for name in required_capabilities if name not in capabilities]
    if missing_caps:
        raise LocalCliIdentityError(
            "required flag missing",
            failure_class="missing_capability",
        )
    events = _reported_str_tuple(record, "events")
    if pin.allowed_events:
        # A pinned allowlist makes the events report mandatory: an omitted
        # list would otherwise pass the denylist check vacuously, the same
        # way an omitted version once passed (GitHub #723). A reported empty
        # list still passes -- that is an attestation, not a silence.
        if events is None:
            raise LocalCliIdentityError(
                "identity probe omitted events",
                failure_class="unknown_event",
            )
        unknown = [event for event in events if event not in pin.allowed_events]
        if unknown:
            raise LocalCliIdentityError(
                "unknown event",
                failure_class="unknown_event",
            )
    models = _optional_str_tuple(record, "models")
    if requested_model is not None and requested_model not in models:
        raise LocalCliIdentityError(
            "requested model drift",
            failure_class="model_drift",
        )


def _optional_str(record: Mapping[str, Any], field_name: str) -> str | None:
    value = record.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise LocalCliIdentityError(
            "identity probe framing",
            failure_class="probe_framing",
        )
    return value


def _optional_str_tuple(record: Mapping[str, Any], field_name: str) -> tuple[str, ...]:
    reported = _reported_str_tuple(record, field_name)
    return () if reported is None else reported


def _reported_str_tuple(
    record: Mapping[str, Any],
    field_name: str,
) -> tuple[str, ...] | None:
    """Return the reported list, or None when the probe omitted the field."""

    value = record.get(field_name)
    if value is None:
        return None
    if not isinstance(value, list):
        raise LocalCliIdentityError(
            "identity probe framing",
            failure_class="probe_framing",
        )
    items: list[str] = []
    for item in cast(list[object], value):
        if not isinstance(item, str) or not item.strip():
            raise LocalCliIdentityError(
                "identity probe framing",
                failure_class="probe_framing",
            )
        items.append(item)
    return tuple(items)


def _kill_process_group(process: subprocess.Popen[bytes]) -> None:
    pid = process.pid
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        return
