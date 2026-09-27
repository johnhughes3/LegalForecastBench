"""Pinned Hermes community command adapter with host-owned task tools."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from legalforecast._json_io import read_json_object_safe, write_json_object
from legalforecast.evals.output_parser import ParserStatus, parse_model_output
from legalforecast.multiharness.host_environment import (
    build_host_subprocess_environment,
)
from legalforecast.multiharness.solver_inputs import SOLVER_INPUT_ENTRY_PATH
from legalforecast.multiharness.spec import (
    TOOL_REQUEST_SCHEMA_VERSION,
    AdapterCapabilities,
    ArtifactRecord,
    RunRequest,
    RunResult,
)
from legalforecast.multiharness.validation import validate_public_record

ADAPTER_ID = "hermes-agent"
ADAPTER_VERSION = "1.0.0"
HERMES_TAG = "v2026.9.24"
HERMES_COMMIT = "f97608f178d1ffeca59860195ab7da295f7c8e5f"
HERMES_VERSION = "0.21.5"
PROVIDER_KEY = "OPENROUTER_API_KEY"


class HermesAdapterError(RuntimeError):
    """A runtime or output violated the pinned bridge contract."""


def adapter_bundle_sha256() -> str:
    """Bind resume and public provenance to both halves of this adapter."""

    digest = hashlib.sha256()
    for name in ("hermes_agent.py", "hermes_runtime.py"):
        digest.update(name.encode() + b"\0")
        digest.update(Path(__file__).with_name(name).read_bytes())
    return "sha256:" + digest.hexdigest()


def capabilities() -> AdapterCapabilities:
    """Advertise the LFB-only, host-tool bridge."""

    return AdapterCapabilities(
        adapter_id=ADAPTER_ID,
        adapter_version=ADAPTER_VERSION,
        supported_families=("legalforecast_mtd",),
        supported_scoring_modes=("lfb_brier",),
        supports_sandbox_policy=True,
        tool_protocol_version=TOOL_REQUEST_SCHEMA_VERSION,
        capabilities_sha256=adapter_bundle_sha256(),
    )


def validate_checkout(checkout: Path) -> Path:
    """Require the frozen release, clean source, and no project credentials."""

    checkout = checkout.resolve(strict=True)

    def git(*args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(checkout), *args],
            check=True,
            stdout=subprocess.PIPE,
            text=True,
            timeout=15,
        )
        return result.stdout.strip()

    if (
        git("rev-parse", "HEAD") != HERMES_COMMIT
        or git("rev-parse", f"{HERMES_TAG}^{{commit}}") != HERMES_COMMIT
    ):
        raise HermesAdapterError("Hermes release tag/commit does not match the pin")
    if git("status", "--porcelain", "--untracked-files=all"):
        raise HermesAdapterError("Hermes checkout must be clean")
    if (checkout / ".env").exists() or (checkout / ".env").is_symlink():
        raise HermesAdapterError("Hermes checkout must not contain project credentials")
    interpreter = checkout / ".venv" / "bin" / "python"
    if not interpreter.is_file():
        raise HermesAdapterError(
            "install the pinned Hermes lock with Python 3.13 first"
        )
    return interpreter


def run(request: RunRequest, workspace: Path, checkout: Path) -> RunResult:
    """Run a fresh managed Hermes conversation using the parent's tool channel."""

    if (request.adapter.adapter_id, request.adapter.adapter_version) != (
        ADAPTER_ID,
        ADAPTER_VERSION,
    ) or (request.task.family, request.task.scoring_mode) != (
        "legalforecast_mtd",
        "lfb_brier",
    ):
        raise HermesAdapterError("unsupported adapter or task contract")
    if request.sandbox_policy.allowed_provider_env_vars != (PROVIDER_KEY,):
        raise HermesAdapterError("only OPENROUTER_API_KEY may be granted")
    if not request.model_key.startswith("openrouter:") or not request.model_key[11:]:
        raise HermesAdapterError("model must use openrouter:<model>")
    units = request.task.metadata.get("required_unit_ids")
    if (
        not isinstance(units, list | tuple)
        or not units
        or any(
            not isinstance(unit, str) or not unit.strip()
            for unit in cast(Sequence[object], units)
        )
    ):
        raise HermesAdapterError("required_unit_ids must contain non-empty strings")
    required_units = list(cast(Sequence[str], units))
    if len(set(required_units)) != len(required_units):
        raise HermesAdapterError("required_unit_ids must be unique")
    interpreter = validate_checkout(checkout)
    private_logs = workspace.resolve() / "private-logs"
    private_logs.mkdir(mode=0o700, parents=True, exist_ok=True)
    attempt = Path(tempfile.mkdtemp(prefix="hermes-", dir=private_logs))
    environment = build_host_subprocess_environment(attempt, (PROVIDER_KEY,))
    hermes_home = attempt / "profile"
    hermes_home.mkdir(mode=0o700)
    environment["HERMES_HOME"] = str(hermes_home)
    environment["HERMES_GUEST_ONBOARDING"] = "0"
    environment["HERMES_IGNORE_RULES"] = "1"
    environment["HERMES_SAFE_MODE"] = "1"
    # JSON is valid YAML. A fresh profile has no plugins, MCP, or saved auth.
    write_json_object(
        hermes_home / "config.yaml",
        {
            "memory": {"memory_enabled": False, "user_profile_enabled": False},
            "plugins": {"enabled": []},
            "mcp_servers": {},
            "platform_toolsets": {"cli": ["legalforecast"]},
            "tools": {"tool_search": {"enabled": "off"}},
        },
    )
    session_id = str(uuid.uuid4())
    config_path = attempt / "request.json"
    write_json_object(
        config_path,
        {
            "checkout": str(checkout.resolve()),
            "request_id": request.request_id,
            "model": request.model_key[11:],
            "required_unit_ids": required_units,
            "session_id": session_id,
            "working_directory": str(attempt),
            "solver_input_path": SOLVER_INPUT_ENTRY_PATH,
        },
    )
    trajectory = attempt / "trajectory.json"
    # Inherit the command adapter's JSONL channel. Hermes' tool handler is the
    # sole writer; runtime diagnostics go to the parent's private stderr log.
    process = subprocess.run(
        [
            str(interpreter),
            str(Path(__file__).with_name("hermes_runtime.py")),
            str(config_path),
            str(trajectory),
        ],
        cwd=attempt,
        env=environment,
        check=False,
        timeout=min(240, request.sandbox_policy.timeout_seconds),
    )
    if process.returncode:
        raise HermesAdapterError("Hermes managed runtime failed")
    if not trajectory.is_file() or trajectory.stat().st_size > 16_777_216:
        raise HermesAdapterError("missing or oversized Hermes trajectory")
    raw = trajectory.read_bytes()
    execution = _read_record(trajectory)
    result = execution.get("result")
    if not isinstance(result, dict):
        raise HermesAdapterError("Hermes result is malformed")
    result = cast(dict[str, object], result)
    if (
        result.get("completed") is not True
        or result.get("failed")
        or result.get("partial")
        or result.get("error")
        or execution.get("session_id") != session_id
        or execution.get("model") != request.model_key[11:]
        or execution.get("tool_call_count") != 1
        or execution.get("hermes_version") != HERMES_VERSION
        or not str(execution.get("python_version", "")).startswith("3.13.")
    ):
        raise HermesAdapterError("Hermes completion or provenance does not match")
    output = result.get("final_response")
    if not isinstance(output, str):
        raise HermesAdapterError("Hermes did not return forecast text")
    parsed = parse_model_output(output, required_unit_ids=required_units)
    if parsed.status != ParserStatus.VALID:
        raise HermesAdapterError("Hermes returned an invalid forecast")
    digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    summary: dict[str, object] = {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "adapter_bundle_sha256": adapter_bundle_sha256(),
        "hermes_version": HERMES_VERSION,
        "hermes_tag": HERMES_TAG,
        "hermes_commit": HERMES_COMMIT,
        "runtime_entrypoint": "AIAgent.run_conversation",
        "python_version": execution["python_version"],
        "auth_mode": "contributor-api-key",
        "provider": "openrouter",
        "requested_model": request.model_key[11:],
        "served_model": result.get("served_model"),
        "served_model_source": "Hermes response header when available",
        "memory_session_policy": "fresh-profile-per-attempt-memory-disabled",
        "enabled_toolsets": ["legalforecast"],
        "tool_call_count": 1,
        "trajectory_sha256": digest,
        "session_sha256": "sha256:" + hashlib.sha256(session_id.encode()).hexdigest(),
        "task_id": request.task.task_id,
    }
    validate_public_record(summary, "hermes.public_summary")
    commitment = json.dumps(
        {
            "request": request.request_sha256,
            "parsed": parsed.to_record(),
            "summary": summary,
        },
        sort_keys=True,
    ).encode()
    return RunResult(
        result_id=f"{request.request_id}:hermes",
        request_id=request.request_id,
        status="succeeded",
        result_sha256="sha256:" + hashlib.sha256(commitment).hexdigest(),
        public_summary=summary,
        artifacts=(
            ArtifactRecord(
                artifact_id="hermes-private-trajectory",
                path=trajectory.relative_to(workspace.resolve()).as_posix(),
                sha256=digest,
                media_type="application/json",
                public=False,
                size_bytes=len(raw),
            ),
        ),
    )


def _read_record(path: Path) -> dict[str, object]:
    return read_json_object_safe(
        path,
        error_factory=HermesAdapterError,
        missing_message=lambda _: "required adapter record is missing",
        non_object_message=lambda _: "adapter record must be an object",
    )


def main(argv: list[str] | None = None) -> int:
    """Serve the public command adapter protocol; live execution requires tools."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--hermes-checkout",
        type=Path,
        required=True,
        help="Clean pinned Hermes checkout with its locked .venv",
    )
    phases = parser.add_subparsers(dest="phase", required=True)
    caps = phases.add_parser(
        "capabilities", help="Describe supported tasks and tool RPC"
    )
    caps.add_argument("--output", type=Path, required=True)
    for name in ("run", "run-with-tools"):
        phase = phases.add_parser(name)
        phase.add_argument("--request", type=Path, required=True)
        phase.add_argument("--workspace", type=Path, required=True)
        phase.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.phase == "capabilities":
            write_json_object(args.output, capabilities().to_record())
        elif args.phase == "run":
            raise HermesAdapterError("Hermes requires the host-owned live tool channel")
        else:
            request = RunRequest.from_record(_read_record(args.request))
            result = run(request, args.workspace, args.hermes_checkout)
            write_json_object(args.output, result.to_record())
        return 0
    except (HermesAdapterError, OSError, ValueError, subprocess.SubprocessError):
        print(
            "Hermes adapter failed closed; inspect private runtime diagnostics",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
