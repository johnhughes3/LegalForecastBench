"""The explicit OpenClaw choice reuses the protected terminal execution lane."""

from __future__ import annotations

import os
import subprocess
import textwrap
from pathlib import Path

import pytest

WORKFLOW = (
    Path(__file__).resolve().parents[1] / ".github/workflows/run-benchmark.yaml"
).read_text(encoding="utf-8")
TERMINAL = WORKFLOW.split("  run-terminal:\n", 1)[1].split("  run-openai:\n", 1)[0]


def _script(name: str) -> str:
    step = WORKFLOW.split(f"      - name: {name}\n", 1)[1].split("      - name:", 1)[0]
    return textwrap.dedent(step.split("        run: |\n", 1)[1])


def _bash(script: str, **environment: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-c", script],
        env={**os.environ, **environment},
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    ("mode", "model", "case_id", "accepted"),
    [
        ("native", "openai:model", "", True),
        ("native", "anthropic:model", "case-1", False),
        ("claude-code-terminal", "anthropic:model", "case-1", True),
        ("openclaw", "anthropic:model", "case-1", True),
        ("openclaw", "openai:model", "", False),
        ("arbitrary-runtime", "anthropic:model", "", False),
    ],
)
def test_dispatch_closed_enum_and_provider(
    mode: str, model: str, case_id: str, accepted: bool
) -> None:
    script = _script("Validate dispatch identity and bounded values").split(
        "for value in", 1
    )[0]
    result = _bash(
        script, EXECUTION_MODE=mode, MODEL_KEY=model, TERMINAL_CASE_ID=case_id
    )
    assert (result.returncode == 0) is accepted, result.stderr


@pytest.mark.parametrize(
    ("mode", "runtime", "prefix"),
    [
        ("claude-code-terminal", "claude-code", "claude-code"),
        ("openclaw", "openclaw", "openclaw"),
    ],
)
def test_build_selects_only_fixed_runtime_and_passes_image_digest(
    tmp_path: Path, mode: str, runtime: str, prefix: str
) -> None:
    image_id = "sha256:" + "a" * 64
    stub = f"""
docker() {{
  if [[ "$1" == image ]]; then printf '%s\\n' '{image_id}';
  else printf '%s\\n' "$*"; fi
}}
"""
    environment_file = tmp_path / "github-env"
    result = _bash(
        stub + _script("Build pinned terminal runtime and gateway images"),
        EXECUTION_MODE=mode,
        GITHUB_ENV=str(environment_file),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        f"build --pull=false -f infra/{runtime}-runtime/Containerfile "
        f"-t lfb-{runtime}:release .",
        "build --pull=false -f infra/model-gateway-runtime/Containerfile "
        "-t lfb-model-gateway:release .",
    ]
    assert environment_file.read_text().splitlines() == [
        f"LFB_TERMINAL_IMAGE={image_id}",
        f"LFB_TERMINAL_RUN_PREFIX={prefix}",
        f"LFB_GATEWAY_IMAGE={image_id}",
    ]


def test_unknown_runtime_never_invokes_docker(tmp_path: Path) -> None:
    result = _bash(
        "docker() { echo UNEXPECTED_DOCKER; return 99; }\n"
        + _script("Build pinned terminal runtime and gateway images"),
        EXECUTION_MODE="../../untrusted",
        GITHUB_ENV=str(tmp_path / "github-env"),
    )
    assert result.returncode != 0
    assert "UNEXPECTED_DOCKER" not in result.stdout
    assert not (tmp_path / "github-env").exists()


@pytest.mark.parametrize("mode", ["claude-code-terminal", "openclaw"])
def test_descriptor_and_execution_receive_same_explicit_harness(mode: str) -> None:
    stub = "uv() { printf '%s\\n' \"$@\"; }\nmkdir() { :; }\n"
    environment = {
        "EXECUTION_MODE": mode,
        "MODEL_KEY": "anthropic:model",
        "CEILING_MICROUSD": "1000000",
        "ACCOUNT": "test-account",
        "TERMINAL_CASE_ID": "case with spaces",
        "LFB_TERMINAL_IMAGE": "sha256:" + "a" * 64,
        "LFB_GATEWAY_IMAGE": "sha256:" + "b" * 64,
        "LFB_MAX_BUDGET_USD": "1",
        "LFB_TERMINAL_RUN_PREFIX": mode,
        "GITHUB_RUN_ID": "123",
        "GITHUB_RUN_ATTEMPT": "1",
    }
    for step in (
        "Issue protected paid gateway descriptor",
        "Execute scoreless terminal release",
    ):
        result = _bash(stub + _script(step), **environment)
        assert result.returncode == 0, result.stderr
        args = result.stdout.splitlines()
        assert args[args.index("--harness") + 1] == mode
        assert args[args.index("--model-key") + 1] == "anthropic:model"
        if "release-execute" in args:
            assert args[args.index("--case-id") + 1] == "case with spaces"
            assert args[args.index("--image") + 1] == environment["LFB_TERMINAL_IMAGE"]
            assert args[args.index("--auth-profile") + 1] == "published-api-key"


def test_openclaw_keeps_existing_protected_custody_and_scoreless_contract() -> None:
    assert "          - openclaw\n" in WORKFLOW
    assert "inputs.execution_mode == 'openclaw'" in TERMINAL
    assert "startsWith(inputs.model_key, 'anthropic:')" in TERMINAL
    assert "needs.prepare-inputs.result == 'success'" in TERMINAL
    assert "environment: legalforecastbench-official-eval\n" in TERMINAL
    assert "git merge-base --is-ancestor HEAD origin/main" in TERMINAL
    assert (
        'test "$(git rev-parse HEAD)" = "${RELEASE_SHA:-$(git rev-parse HEAD)}"'
        in TERMINAL
    )
    assert "persist-credentials: false" in TERMINAL
    assert "id-token: write" in TERMINAL
    assert "role-to-assume: ${{ env.LFB_GITHUB_PACKET_READ_ROLE_ARN }}" in TERMINAL
    assert (
        "artifact-ids: ${{ needs.prepare-inputs.outputs.locked_inputs_artifact_id }}"
        in TERMINAL
    )
    assert TERMINAL.count("ANTHROPIC_API_KEY:") == 1
    assert "ANTHROPIC_API_KEY" not in _script(
        "Build pinned terminal runtime and gateway images"
    )
    assert "--gateway-upstream-base-url https://api.anthropic.com:443" in TERMINAL
    assert "labels" not in TERMINAL.lower()
    assert "release-score" not in TERMINAL
    assert (
        "official-terminal-forecast-results-${{ github.run_id }}-attempt-"
        "${{ github.run_attempt }}" in TERMINAL
    )
