"""Credential-free validation of the native Claude/Codex adapter interfaces."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path

from legalforecast._json_io import read_json_object
from legalforecast.multiharness.local_cli_identity import (
    ExecutableIdentityPin,
    LocalCliIdentityError,
    ObservedExecutableIdentity,
    bind_executable_identity,
    verify_executable_digest,
)
from legalforecast.multiharness.local_cli_manifest import LocalCliAdapterManifest
from legalforecast.multiharness.local_cli_probe import (
    InstalledCliProbe,
    LocalCliProbeError,
    probe_installed_cli,
)

_MANIFESTS = {
    "claude": "claude-code/local-cli-adapter-manifest.json",
    "codex": "codex-cli/local-cli-manifest.json",
}
_SHORT_FLAGS = {"-p": "--print", "-c": "--config"}


def _manifest(cli: str) -> LocalCliAdapterManifest:
    if cli not in _MANIFESTS:
        raise LocalCliProbeError("native preflight supports only claude and codex")
    path = Path(__file__).resolve().parents[2] / "examples/adapters" / _MANIFESTS[cli]
    return LocalCliAdapterManifest.from_record(
        read_json_object(
            path,
            error_factory=LocalCliProbeError,
            missing_message=lambda _path: "native adapter manifest is missing",
            non_object_message=lambda _path: (
                "native adapter manifest must be an object"
            ),
        )
    )


def preflight_native_cli(
    pin: ExecutableIdentityPin,
    *,
    scratch_root: Path,
    parent_env: Mapping[str, str] | None = None,
    paid: bool = False,
) -> InstalledCliProbe:
    """Require pinned vendor identity and the supported adapter's help flags.

    Only ``--version`` and Claude ``--help`` / Codex ``exec --help`` run.
    This checks parser-advertised options, not provider behavior or terms.
    """

    manifest = _manifest(pin.basename)
    parent = os.environ if parent_env is None else parent_env
    # Refuse substituted bytes before launching even a credential-free probe.
    verify_executable_digest(
        pin, (pin.basename,), search_path=parent.get("PATH", "/usr/bin")
    )
    observed = probe_installed_cli(
        pin,
        help_args=("exec", "--help") if pin.basename == "codex" else ("--help",),
        scratch_root=scratch_root,
        parent_env=parent,
    )
    if not observed.pin_version_match:
        raise LocalCliProbeError("native CLI version does not match the declared pin")
    if not observed.pin_digest_match:
        raise LocalCliProbeError("native CLI digest changed during the probe")
    required = {
        _SHORT_FLAGS.get(token, token)
        for token in manifest.invocation.argv_template
        if token.startswith("--") or token in _SHORT_FLAGS
    }
    required.update(pin.required_flags)
    if paid and pin.basename == "claude":
        required.add("--max-budget-usd")
    missing = required.difference(observed.observed_flags)
    if missing:
        raise LocalCliProbeError(
            "native CLI is missing required flags: " + ", ".join(sorted(missing))
        )
    verify_executable_digest(
        pin, (pin.basename,), search_path=parent.get("PATH", "/usr/bin")
    )
    return observed


def preflight_solver_identity(
    pin: ExecutableIdentityPin,
    *,
    native: bool,
    version_probe_args: Sequence[str],
    scratch_root: Path,
    parent_env: Mapping[str, str] | None,
    requested_model: str,
    paid: bool,
) -> ObservedExecutableIdentity:
    """Select vendor-text preflight without relaxing custom JSON identities."""

    if native and tuple(version_probe_args) == ("--version",):
        preflight_native_cli(
            pin, scratch_root=scratch_root, parent_env=parent_env, paid=paid
        )
        parent = os.environ if parent_env is None else parent_env
        return verify_executable_digest(
            pin, (pin.basename,), search_path=parent.get("PATH", "/usr/bin")
        )
    return bind_executable_identity(
        pin,
        (pin.basename,),
        version_probe_args=version_probe_args,
        scratch_root=scratch_root,
        parent_env=parent_env,
        requested_model=requested_model,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Validate a native CLI pin using only credential-free help/version calls."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cli",
        required=True,
        choices=tuple(_MANIFESTS),
        help="Adapter interface to check on PATH.",
    )
    parser.add_argument(
        "--version",
        help=(
            "Exact intended vendor version; use with --sha256. "
            "Defaults to the example manifest pin."
        ),
    )
    parser.add_argument(
        "--sha256",
        help=(
            "Intended executable SHA-256; use with --version. "
            "No pin is inferred from installed bytes."
        ),
    )
    parser.add_argument(
        "--paid",
        action="store_true",
        help=(
            "Also require Claude's monetary budget flag. Does not authorize "
            "spending or validate Codex spending support."
        ),
    )
    args = parser.parse_args(argv)
    if bool(args.version) != bool(args.sha256):
        parser.error("--version and --sha256 must be supplied together")
    executable = _manifest(args.cli).executable
    try:
        pin = ExecutableIdentityPin(
            basename=args.cli,
            version=args.version or executable.version,
            sha256=args.sha256 or executable.sha256,
        )
        with tempfile.TemporaryDirectory(prefix="lfb-native-preflight-") as scratch:
            observed = preflight_native_cli(
                pin, scratch_root=Path(scratch), paid=args.paid
            )
        print(json.dumps(observed.to_record(), sort_keys=True))
        return 0
    except (LocalCliProbeError, LocalCliIdentityError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
