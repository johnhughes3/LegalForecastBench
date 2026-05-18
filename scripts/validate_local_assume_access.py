#!/usr/bin/env python3
"""Validate local Granted profile access for LegalForecastBench S3 artifacts."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AWS_REGION = "us-east-1"
DEFAULT_PACKET_PREFIX = "model-packets/"
DEFAULT_RESULTS_PREFIX = "manifests/"


@dataclass(frozen=True, slots=True)
class LocalAccessConfig:
    aws_region: str
    s3_profile: str
    packet_bucket: str
    results_bucket: str
    packet_prefix: str
    results_prefix: str
    dry_run: bool


def build_assume_shell_command(profile: str, aws_command: Sequence[str]) -> str:
    """Build the zsh command that loads John's Granted `assume` alias."""
    command_text = " ".join(shlex.quote(part) for part in aws_command)
    return f"assume {shlex.quote(profile)} --exec {shlex.quote(command_text)}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate local LegalForecastBench AWS access through Granted assume "
            "without printing bucket names or account IDs."
        )
    )
    parser.add_argument(
        "--aws-region",
        default=os.environ.get("LFB_AWS_REGION", DEFAULT_AWS_REGION),
        help="AWS region for validation calls; defaults to LFB_AWS_REGION.",
    )
    parser.add_argument(
        "--s3-profile",
        default=os.environ.get("LFB_LOCAL_S3_ASSUME_PROFILE", ""),
        help="Granted profile used for packet/result bucket checks.",
    )
    parser.add_argument(
        "--packet-prefix",
        default=os.environ.get("LFB_MODEL_PACKET_PREFIX", DEFAULT_PACKET_PREFIX),
        help="Packet bucket prefix to list.",
    )
    parser.add_argument(
        "--results-prefix",
        default=os.environ.get("LFB_RESULTS_MANIFEST_PREFIX", DEFAULT_RESULTS_PREFIX),
        help="Results bucket prefix to list.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned profile/prefix checks without calling AWS.",
    )
    args = parser.parse_args(argv)

    try:
        config = config_from_env(vars(args), os.environ)
        validate_config(config)
        if config.dry_run:
            print_plan(config)
            return 0
        run_checks(config)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


def config_from_env(
    args: Mapping[str, object],
    env: Mapping[str, str],
) -> LocalAccessConfig:
    packet_bucket = env.get("LFB_PACKET_BUCKET", "").strip()
    results_bucket = env.get("LFB_RESULTS_BUCKET", "").strip()
    missing = [
        name
        for name, value in (
            ("LFB_PACKET_BUCKET", packet_bucket),
            ("LFB_RESULTS_BUCKET", results_bucket),
        )
        if value == ""
    ]
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(f"missing required environment variable(s): {joined}")

    s3_profile = str(args["s3_profile"]).strip()
    missing_profiles: list[str] = []
    if s3_profile == "":
        missing_profiles.append("LFB_LOCAL_S3_ASSUME_PROFILE")
    if missing_profiles:
        joined = ", ".join(missing_profiles)
        raise RuntimeError(f"missing required environment variable(s): {joined}")

    return LocalAccessConfig(
        aws_region=str(args["aws_region"]),
        s3_profile=s3_profile,
        packet_bucket=packet_bucket,
        results_bucket=results_bucket,
        packet_prefix=str(args["packet_prefix"]),
        results_prefix=str(args["results_prefix"]),
        dry_run=bool(args["dry_run"]),
    )


def validate_config(config: LocalAccessConfig) -> None:
    if config.s3_profile == "":
        raise RuntimeError("S3 artifact validation requires a local assume profile.")


def print_plan(config: LocalAccessConfig) -> None:
    print(f"packet bucket prefix: assume {config.s3_profile} -> {config.packet_prefix}")
    print(
        f"results bucket prefix: assume {config.s3_profile} -> {config.results_prefix}"
    )


def run_checks(config: LocalAccessConfig) -> None:
    secrets = (config.packet_bucket, config.results_bucket)
    packet_payload = _run_assume_json(
        profile=config.s3_profile,
        aws_command=(
            "aws",
            "s3api",
            "list-objects-v2",
            "--bucket",
            config.packet_bucket,
            "--prefix",
            config.packet_prefix,
            "--max-keys",
            "1",
            "--region",
            config.aws_region,
            "--output",
            "json",
        ),
        label="packet bucket prefix",
        secrets=secrets,
    )
    packet_count = _key_count(packet_payload, label="packet bucket prefix")
    print(
        "packet bucket prefix: "
        f"assume {config.s3_profile} -> {config.packet_prefix} ok "
        f"(KeyCount={packet_count})"
    )

    results_payload = _run_assume_json(
        profile=config.s3_profile,
        aws_command=(
            "aws",
            "s3api",
            "list-objects-v2",
            "--bucket",
            config.results_bucket,
            "--prefix",
            config.results_prefix,
            "--max-keys",
            "1",
            "--region",
            config.aws_region,
            "--output",
            "json",
        ),
        label="results bucket prefix",
        secrets=secrets,
    )
    results_count = _key_count(results_payload, label="results bucket prefix")
    print(
        "results bucket prefix: "
        f"assume {config.s3_profile} -> {config.results_prefix} ok "
        f"(KeyCount={results_count})"
    )


def _run_assume_json(
    *,
    profile: str,
    aws_command: Sequence[str],
    label: str,
    secrets: Sequence[str],
) -> dict[str, object]:
    shell_command = build_assume_shell_command(profile, aws_command)
    completed = subprocess.run(
        ("zsh", "-lic", shell_command),
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.stdout.strip() == "":
        stderr = _sanitize(completed.stderr, secrets)
        raise RuntimeError(
            f"{label} check returned no JSON output through assume {profile}. "
            f"stderr: {stderr or '<empty>'}"
        )
    return _json_object(
        completed.stdout,
        label=label,
        stderr=completed.stderr,
        secrets=secrets,
    )


def _json_object(
    text: str,
    *,
    label: str,
    stderr: str,
    secrets: Sequence[str],
) -> dict[str, object]:
    try:
        payload: object = json.loads(text)
    except json.JSONDecodeError as exc:
        sanitized_output = _sanitize(text, secrets)
        sanitized_stderr = _sanitize(stderr, secrets)
        raise RuntimeError(
            f"{label} check did not return valid JSON. "
            f"stdout: {sanitized_output or '<empty>'}; "
            f"stderr: {sanitized_stderr or '<empty>'}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{label} check returned JSON that is not an object")
    return cast(dict[str, object], payload)


def _key_count(payload: Mapping[str, object], *, label: str) -> int:
    key_count = payload.get("KeyCount")
    if not isinstance(key_count, int):
        raise RuntimeError(f"{label} check did not return an integer KeyCount")
    return key_count


def _sanitize(text: str, secrets: Sequence[str]) -> str:
    sanitized = text.strip()
    for secret in secrets:
        if secret:
            sanitized = sanitized.replace(secret, "<bucket>")
    sanitized = re.sub(r"\b\d{12}\b", "<aws-account-id>", sanitized)
    return sanitized[-800:]


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
