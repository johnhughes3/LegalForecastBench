from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_local_assume_script_uses_env_provided_split_profiles() -> None:
    module = _load_script_module()
    config = module.config_from_env(
        {
            "aws_region": "us-east-1",
            "bedrock_profile": "bedrock-runtime-profile",
            "s3_profile": "artifact-s3-profile",
            "packet_prefix": module.DEFAULT_PACKET_PREFIX,
            "results_prefix": module.DEFAULT_RESULTS_PREFIX,
            "skip_bedrock_identity": False,
            "dry_run": False,
        },
        {
            "LFB_PACKET_BUCKET": "packet-bucket",
            "LFB_RESULTS_BUCKET": "results-bucket",
        },
    )

    assert config.bedrock_profile == "bedrock-runtime-profile"
    assert config.s3_profile == "artifact-s3-profile"
    module.validate_config(config)


def test_local_assume_script_rejects_bedrock_profile_for_s3() -> None:
    module = _load_script_module()
    config = module.LocalAccessConfig(
        aws_region="us-east-1",
        bedrock_profile="bedrock-runtime-profile",
        s3_profile="bedrock-runtime-profile",
        packet_bucket="packet-bucket",
        results_bucket="results-bucket",
        packet_prefix="model-packets/",
        results_prefix="manifests/",
        skip_bedrock_identity=False,
        dry_run=False,
    )

    with pytest.raises(RuntimeError, match="distinct artifacts profile"):
        module.validate_config(config)


def test_local_assume_script_requires_profile_names_from_environment() -> None:
    module = _load_script_module()

    with pytest.raises(RuntimeError, match="LFB_BEDROCK_ASSUME_PROFILE"):
        module.config_from_env(
            {
                "aws_region": "us-east-1",
                "bedrock_profile": "",
                "s3_profile": "",
                "packet_prefix": module.DEFAULT_PACKET_PREFIX,
                "results_prefix": module.DEFAULT_RESULTS_PREFIX,
                "skip_bedrock_identity": False,
                "dry_run": False,
            },
            {
                "LFB_PACKET_BUCKET": "packet-bucket",
                "LFB_RESULTS_BUCKET": "results-bucket",
            },
        )


def test_local_assume_script_builds_granted_exec_command_without_secrets() -> None:
    module = _load_script_module()
    command = module.build_assume_shell_command(
        "artifact-s3-profile",
        (
            "aws",
            "s3api",
            "list-objects-v2",
            "--bucket",
            "private-packet-bucket",
            "--prefix",
            "model-packets/",
        ),
    )

    assert command.startswith("assume artifact-s3-profile --exec ")
    assert "aws s3api list-objects-v2" in command


def test_local_assume_script_sanitizes_private_details() -> None:
    module = _load_script_module()

    sanitized = module._sanitize(
        "bucket private-packet-bucket account 123456789012",
        ("private-packet-bucket",),
    )

    assert "private-packet-bucket" not in sanitized
    assert "123456789012" not in sanitized
    assert "<bucket>" in sanitized
    assert "<aws-account-id>" in sanitized


def _load_script_module() -> ModuleType:
    script_path = ROOT / "scripts" / "validate_local_assume_access.py"
    spec = importlib.util.spec_from_file_location(
        "validate_local_assume_access", script_path
    )
    if spec is None or spec.loader is None:
        raise AssertionError("could not load validate_local_assume_access.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module
