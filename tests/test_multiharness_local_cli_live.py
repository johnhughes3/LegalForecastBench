"""Live, env-gated checks for Infisical path binding and one real Claude call."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from legalforecast.multiharness.auth_profiles import (
    PUBLISHED_API_KEY,
    AuthProfileError,
    infisical_path_for_profile,
    resolve_auth_profile,
)
from legalforecast.multiharness.local_cli_environment import (
    InfisicalSandboxCredentialSource,
    StaticCredentialSource,
)
from legalforecast.multiharness.local_cli_runtime import (
    LocalCliAdapterManifest,
    LocalCliRunSpec,
    LocalCliRuntimeError,
    execute_local_cli,
)

_WRAPPER_NAME = "infisical-agent-sandbox"
_NAMESPACE_ROOT = "/agents/sandbox/legalforecastbench"
_DECLARED_PATH = infisical_path_for_profile(PUBLISHED_API_KEY)
_SIBLING_PATH = "/agents/sandbox/legalforecastbench/harness-runtime/undeclared-sibling"
_BOOLEAN_PROBE = (
    "import json, os, sys;"
    "names = [item for item in sys.argv[1].split(',') if item];"
    "print(json.dumps({name: bool(os.environ.get(name)) for name in names},"
    " sort_keys=True))"
)
_PROBE_NAMES = "ANTHROPIC_API_KEY,OPENAI_API_KEY,CLAUDE_CODE_OAUTH_TOKEN"
_LIVE_PROMPT = "Reply with the single word ping and nothing else."


def test_live_infisical_wrapper_reads_declared_path_not_sibling() -> None:
    wrapper = shutil.which(_WRAPPER_NAME)
    if wrapper is None:
        pytest.skip(f"{_WRAPPER_NAME} is not on PATH")
    assert Path(wrapper).name == _WRAPPER_NAME
    assert Path(wrapper).name != "infisical"

    root_rc, root_present = _wrapper_boolean_probe(wrapper, _NAMESPACE_ROOT)
    declared_rc, declared_present = _wrapper_boolean_probe(wrapper, _DECLARED_PATH)
    sibling_rc, sibling_present = _wrapper_boolean_probe(wrapper, _SIBLING_PATH)

    assert _SIBLING_PATH != _DECLARED_PATH
    assert _DECLARED_PATH.startswith(f"{_NAMESPACE_ROOT}/")
    assert root_rc == 0
    assert root_present is not None
    assert not any(root_present.values())
    assert sibling_rc != 0
    assert sibling_present is None
    if declared_rc == 0:
        assert declared_present is not None
        assert set(declared_present) <= {
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "CLAUDE_CODE_OAUTH_TOKEN",
        }
    else:
        assert declared_present is None


@pytest.mark.lfb_live_smoke
def test_live_claude_through_execution_service(tmp_path: Path) -> None:
    claude = shutil.which("claude")
    if claude is None:
        pytest.skip("claude binary is not on PATH")
    wrapper = shutil.which(_WRAPPER_NAME)
    if wrapper is None:
        pytest.skip(f"{_WRAPPER_NAME} is not on PATH")

    profile = resolve_auth_profile(
        PUBLISHED_API_KEY,
        supported_profiles=(PUBLISHED_API_KEY,),
        projected_env_vars=("ANTHROPIC_API_KEY",),
    )
    source = InfisicalSandboxCredentialSource(wrapper_path=Path(wrapper))
    try:
        projected = dict(source.fetch_projected_env(profile))
    except AuthProfileError:
        pytest.skip(
            "declared published-api-key Infisical path did not project "
            "ANTHROPIC_API_KEY"
        )
    secret = projected.get("ANTHROPIC_API_KEY", "")
    if not secret:
        pytest.skip("declared published-api-key Infisical path is empty")
    static = StaticCredentialSource(dict(projected))

    scratch = tmp_path / "live-claude"
    parent = {
        "PATH": os.environ.get("PATH", "/usr/bin"),
        "LC_CTYPE": os.environ.get("LC_CTYPE", "C.UTF-8"),
        "HOME": os.environ.get("HOME", str(tmp_path / "operator-home")),
        "ANTHROPIC_API_KEY": "canary",
        "OPENAI_API_KEY": "ambient-openai-canary",
        "OP_SERVICE_ACCOUNT_TOKEN": "canary-op-token-value",
        "CANARY_AWS_KEY": "canary-aws-key-value",
    }
    try:
        result = execute_local_cli(
            LocalCliRunSpec(
                spec_id="live-claude-haiku",
                manifest=LocalCliAdapterManifest(
                    adapter_id="claude-live",
                    display_name="Claude Code",
                    adapter_version="live",
                    command=(claude,),
                    supported_auth_profiles=(PUBLISHED_API_KEY,),
                    profile_env_vars=((PUBLISHED_API_KEY, ("ANTHROPIC_API_KEY",)),),
                ),
                auth_profile=PUBLISHED_API_KEY,
                extra_args=(
                    "-p",
                    "--output-format",
                    "json",
                    "--model",
                    os.environ.get(
                        "LFB_LIVE_CLAUDE_MODEL", "claude-haiku-4-5-20251001"
                    ),
                    _LIVE_PROMPT,
                ),
                timeout_seconds=120,
            ),
            scratch,
            credential_source=static,
            parent_env=parent,
        )
    except LocalCliRuntimeError as exc:
        message = str(exc)
        assert "canary" not in message
        assert "ambient-openai-canary" not in message
        raise

    transcript = scratch / "transcript.json"
    transcript.write_bytes(result.stdout)
    public = result.to_public_record()
    assert result.status == "completed"
    assert result.exit_code == 0
    assert result.stdout
    assert result.duration_ms > 0
    assert result.cost_usd is not None
    assert result.cost_usd >= 0
    assert public["duration_ms"] == result.duration_ms
    assert public["cost_usd"] == result.cost_usd
    persisted = transcript.read_text(encoding="utf-8")
    public_text = json.dumps(public)
    leaked = secret in persisted or secret in public_text
    secret = ""
    projected.clear()
    assert leaked is False
    for canary in (
        "ambient-openai-canary",
        "canary-op-token-value",
        "canary-aws-key-value",
    ):
        canary_leaked = canary in persisted or canary in public_text
        assert canary_leaked is False
    cost_path = scratch / "live-cost.json"
    cost_path.write_text(
        json.dumps({"cost_usd": result.cost_usd, "duration_ms": result.duration_ms}),
        encoding="utf-8",
    )


def _wrapper_boolean_probe(
    wrapper: str,
    infisical_path: str,
) -> tuple[int, dict[str, bool] | None]:
    completed = subprocess.run(
        (
            wrapper,
            "run",
            "--env",
            "dev",
            "--path",
            infisical_path,
            "--",
            sys.executable,
            "-c",
            _BOOLEAN_PROBE,
            _PROBE_NAMES,
        ),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=30,
        check=False,
        env={
            "PATH": os.environ.get("PATH", "/usr/bin"),
            "LC_CTYPE": os.environ.get("LC_CTYPE", "C.UTF-8"),
            "HOME": os.environ.get("HOME", ""),
        },
    )
    returncode = completed.returncode
    stdout = completed.stdout
    del completed
    if returncode != 0:
        return returncode, None
    try:
        decoded = json.loads(stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return returncode, None
    if not isinstance(decoded, dict):
        return returncode, None
    present: dict[str, bool] = {}
    for key, value in decoded.items():
        if not isinstance(key, str) or not isinstance(value, bool):
            return returncode, None
        present[key] = value
    return returncode, present
