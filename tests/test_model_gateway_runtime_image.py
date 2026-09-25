"""Provider-free model-gateway runtime image producer checks."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

RUNTIME_ROOT = Path(__file__).resolve().parents[1] / "infra" / "model-gateway-runtime"
CONTAINERFILE = RUNTIME_ROOT / "Containerfile"
UV_IMAGE_DIGEST = (
    "sha256:606e70c71c852d03f611b1e56a195d08648507018a7057fab82c4974c4eae105"
)
PYTHON_IMAGE_DIGEST = (
    "sha256:31da4cb527055e4e3d7e9e006dffe9329f84ebea79eaca0a1f1c27ce61e40ca5"
)


def test_containerfile_is_locked_and_provider_free() -> None:
    containerfile = CONTAINERFILE.read_text(encoding="utf-8")

    assert f"ghcr.io/astral-sh/uv:0.12.0@{UV_IMAGE_DIGEST}" in containerfile
    assert f"python:3.14.2-alpine3.23@{PYTHON_IMAGE_DIGEST}" in containerfile
    assert containerfile.count("uv sync --locked --no-dev") == 2
    assert "--no-editable" in containerfile
    assert "aws-cli=2.32.7-r0" in containerfile
    assert "COPY --from=build /opt/legalforecast/.venv" in containerfile
    assert "ANTHROPIC_API_KEY" not in containerfile
    assert "AWS_ACCESS_KEY_ID" not in containerfile
    assert "AWS_SECRET_ACCESS_KEY" not in containerfile


def test_runtime_readme_names_the_network_and_credential_boundary() -> None:
    readme = (RUNTIME_ROOT / "README.md").read_text(encoding="utf-8")

    assert "contains no API key, AWS credential" in readme
    assert "does not enforce network egress" in readme
    assert "--network none" in readme
    assert "will not provide that import closure" in readme


@pytest.mark.skipif(
    not os.environ.get("LEGALFORECAST_MODEL_GATEWAY_RUNTIME_IMAGE"),
    reason="set LEGALFORECAST_MODEL_GATEWAY_RUNTIME_IMAGE to run the built-image smoke",
)
def test_built_image_has_locked_imports_and_aws_cli_without_network() -> None:
    image = os.environ["LEGALFORECAST_MODEL_GATEWAY_RUNTIME_IMAGE"]
    completed = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--entrypoint",
            "/bin/sh",
            image,
            "-eu",
            "-c",
            "aws --version 2>&1 && "
            "python3 -c 'import "
            "legalforecast.evals.provider_spend_control, "
            "legalforecast.multiharness.protected_terminal_paid'",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, (
        "built image smoke failed\n"
        f"stdout={completed.stdout}\n"
        f"stderr={completed.stderr}"
    )
    assert "aws-cli/2." in f"{completed.stdout}\n{completed.stderr}"
