from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/run-benchmark.yaml").read_text(encoding="utf-8")
LEGACY = ROOT / ".github/workflows/run-benchmark-manifest.yaml"
ROOTLESS_SETUP = ROOT / ".github/scripts/setup-rootless-docker.sh"
ROOTLESS_SMOKE = (
    ROOT / ".github/workflows/rootless-tool-runtime-smoke.yaml"
).read_text(encoding="utf-8")


def _job(name: str, next_name: str | None = None) -> str:
    start = WORKFLOW.index(f"  {name}:")
    end = WORKFLOW.index(f"  {next_name}:", start) if next_name else len(WORKFLOW)
    return WORKFLOW[start:end]


def test_canonical_dispatcher_partitions_dynamic_provider_lanes() -> None:
    assert not LEGACY.exists()
    assert "run-openai:" in WORKFLOW
    assert "run-anthropic:" in WORKFLOW
    assert "run-gemini:" in WORKFLOW
    for provider, next_name in (
        ("openai", "run-anthropic"),
        ("anthropic", "run-gemini"),
        ("gemini", None),
    ):
        job = _job(f"run-{provider}", next_name)
        assert "environment: legalforecastbench-official-eval" in job
        assert "Download outcome-blinded inputs" in job
        assert "fromJSON(needs.prepare-inputs.outputs." + provider + "_matrix)" in job


def test_provider_credentials_are_step_scoped_and_never_inherited() -> None:
    jobs = {
        "run-openai": ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"),
        "run-anthropic": ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"),
        "run-gemini": ("GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"),
    }
    next_names = {
        "run-openai": "run-anthropic",
        "run-anthropic": "run-gemini",
        "run-gemini": None,
    }
    for name, (own, other_a, other_b) in jobs.items():
        block = _job(name, next_names[name])
        assert block.count(f"secrets.{own}") == 1
        assert f"secrets.{other_a}" not in block
        assert f"secrets.{other_b}" not in block
        assert "secrets: inherit" not in block
        assert "LFB_GITHUB_FAN_IN_ROLE_ARN" not in block


def test_provider_cells_have_no_label_input_or_scoring_authority() -> None:
    for name, next_name in (
        ("run-openai", "run-anthropic"),
        ("run-anthropic", "run-gemini"),
        ("run-gemini", None),
    ):
        block = _job(name, next_name)
        assert "labels_release_uri" not in block
        assert "LABELS" not in block
        assert "--labels" not in block
        assert "score" not in block.lower()
        assert "report" not in block.lower()
        assert "GITHUB_EVENT_PATH" not in block


def test_provider_cells_use_durable_resume_state_and_exact_source_checks() -> None:
    for name, next_name in (
        ("run-openai", "run-anthropic"),
        ("run-anthropic", "run-gemini"),
        ("run-gemini", None),
    ):
        block = _job(name, next_name)
        # origin/main must be resolvable by the time the source check runs, but
        # NOT via a separate `git fetch`: the checkout step sets
        # persist-credentials: false, so no later step holds a token, and a
        # bare fetch against this repository dies with
        # "could not read Username for 'https://github.com'"
        # (legalforecastbench-2x9o). fetch-depth: 0 makes the checkout action
        # itself fetch full history and refs (including origin/main) under its
        # own short-lived credentials instead.
        assert "fetch-depth: 0" in block
        assert "persist-credentials: false" in block
        assert "git fetch --no-tags --depth=1 origin main" not in block
        assert "git merge-base --is-ancestor HEAD origin/main" in block
        assert "Restore prior completed cell state" in block
        assert "Recover saved managed transcript for provider-free replay" in block
        assert "scripts/recover_managed_transcript.py" in block
        assert "Persist" in block
        assert "if: ${{ always() }}" in block
        assert "ledger.sqlite3" in block
        assert "receipts" in block
        assert "transcripts" in block
        assert "failure-summary.json" in block
        assert "if-no-files-found: error" in block
        assert "--cell-id" in block
        assert "--unit-id" in block


def test_workflow_action_references_are_full_sha_pinned() -> None:
    references = re.findall(
        r"^\s*uses:\s+([^@\s]+)@([^\s#]+)", WORKFLOW, flags=re.MULTILINE
    )
    assert references
    for action, revision in references:
        assert re.fullmatch(r"[0-9a-f]{40}", revision), (action, revision)


def test_openai_document_tools_build_and_run_on_selected_rootless_daemon() -> None:
    job = _job("run-openai", "run-anthropic")
    setup_at = job.index("Configure rootless Docker for document tools")
    build_at = job.index("Build isolated document tool image")
    execute_at = job.index("Execute exact OpenAI forecast cell")
    assert setup_at < build_at < execute_at
    assert job.count(".github/scripts/setup-rootless-docker.sh") == 1
    assert job.count("docker build -f infra/tool-runtime/Containerfile") == 1
    assert "LFB_HARVEY_TOOL_IMAGE=${tool_image_id}" in job

    setup = ROOTLESS_SETUP.read_text(encoding="utf-8")
    for name in ("XDG_RUNTIME_DIR", "DOCKER_HOST", "LFB_CONTAINER_BACKEND"):
        assert f"{name}=" in setup
    assert "env -i" in setup
    assert "dockerd-rootless.sh" in setup
    assert "--exec-opt native.cgroupdriver=cgroupfs" in setup
    assert "docker-ce-rootless-extras=${docker_version}" in setup

    assert "runs-on: ubuntu-latest" in ROOTLESS_SMOKE
    assert ".github/scripts/setup-rootless-docker.sh" in ROOTLESS_SMOKE
    assert "infra/tool-runtime/Containerfile" in ROOTLESS_SMOKE
    assert "open_official_tool_session" in ROOTLESS_SMOKE
    assert "must-not-reach-tool-container" in ROOTLESS_SMOKE


def test_rootless_setup_replaces_rootful_backend_and_scrubs_daemon_environment(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    daemon_environment = tmp_path / "daemon-environment"
    daemon_ready = tmp_path / "daemon-ready"
    sudo_log = tmp_path / "sudo.log"
    quoted_daemon_environment = shlex.quote(str(daemon_environment))
    quoted_daemon_ready = shlex.quote(str(daemon_ready))
    quoted_fake_bin = shlex.quote(str(fake_bin))
    quoted_sudo_log = shlex.quote(str(sudo_log))

    def executable(name: str, body: str) -> None:
        path = fake_bin / name
        path.write_text("#!/usr/bin/bash\nset -euo pipefail\n" + body, encoding="utf-8")
        path.chmod(0o755)

    for command in (
        "awk",
        "cat",
        "chmod",
        "env",
        "id",
        "mkdir",
        "rm",
        "sleep",
        "sort",
        "touch",
    ):
        (fake_bin / command).symlink_to(Path("/usr/bin") / command)
    (fake_bin / "bash").symlink_to("/usr/bin/bash")

    executable(
        "grep",
        """
if [[ " $* " == *" -RqsF "* ]] \
  && [[ "$*" == *"download.docker.com/linux/ubuntu"* ]]; then
  exit 0
fi
exec /usr/bin/grep "$@"
""",
    )

    executable(
        "docker",
        f"""
if [[ "${{1:-}}" == "info" ]]; then
  if [[ -f {quoted_daemon_ready} ]]; then
    printf '%s\\n' '["name=seccomp","name=rootless"]'
  else
    printf '%s\\n' '["name=seccomp"]'
  fi
  exit 0
fi
exit 64
""",
    )
    executable(
        "curl",
        """
destination=""
while (($#)); do
  if [[ "$1" == "-o" ]]; then destination="$2"; shift 2; else shift; fi
done
printf 'test-key' >"${destination}"
""",
    )
    executable(
        "gpg",
        """
while (($#)); do
  if [[ "$1" == "--output" ]]; then output="$2"; shift 2; else shift; fi
done
printf 'test-keyring' >"${output}"
""",
    )
    executable(
        "dpkg",
        '[[ "${1:-}" == "--print-architecture" ]] && printf \'amd64\\n\'',
    )
    executable(
        "dpkg-query",
        "printf '%s\\n' '5:28.0.4-1~ubuntu.24.04~noble'",
    )
    executable(
        "sudo",
        f"""
printf '%s\\n' "$*" >>{quoted_sudo_log}
case "${{1:-}}" in
  install) exit 0 ;;
  tee) cat >/dev/null; exit 0 ;;
  *) exec "$@" ;;
esac
""",
    )
    executable(
        "apt-get",
        f"""
if [[ " $* " == *" install "* ]]; then
  for command in newuidmap newgidmap rootlesskit slirp4netns; do
    printf '%s\\n' '#!/usr/bin/bash' 'exit 0' >{quoted_fake_bin}/"${{command}}"
    /usr/bin/chmod 0755 {quoted_fake_bin}/"${{command}}"
  done
  cat >{quoted_fake_bin}/dockerd-rootless.sh <<'SCRIPT'
#!/usr/bin/bash
env | sort >__DAEMON_ENVIRONMENT__
touch __DAEMON_READY__
exec /usr/bin/tail -f /dev/null
SCRIPT
  /usr/bin/sed -i \
    -e 's|__DAEMON_ENVIRONMENT__|{quoted_daemon_environment}|g' \
    -e 's|__DAEMON_READY__|{quoted_daemon_ready}|g' \
    {quoted_fake_bin}/dockerd-rootless.sh
  /usr/bin/chmod 0755 {quoted_fake_bin}/dockerd-rootless.sh
fi
""",
    )

    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    github_environment = tmp_path / "github-env"
    environment = {
        "PATH": str(fake_bin),
        "HOME": str(tmp_path / "home"),
        "RUNNER_TEMP": str(runner_temp),
        "GITHUB_ENV": str(github_environment),
        "AWS_SECRET_ACCESS_KEY": "must-not-reach-daemon",
        "OPENAI_API_KEY": "must-not-reach-daemon",
    }
    Path(environment["HOME"]).mkdir()
    completed = subprocess.run(
        (str(ROOTLESS_SETUP),),
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )
    daemon_pid_path = runner_temp / "lfb-dkr/daemon-launcher.pid"
    try:
        assert completed.returncode == 0, completed.stderr
        exported = github_environment.read_text(encoding="utf-8")
        runtime_directory = runner_temp / "lfb-dkr/run"
        assert f"XDG_RUNTIME_DIR={runtime_directory}\n" in exported
        assert f"DOCKER_HOST=unix://{runtime_directory}/docker.sock\n" in exported
        assert "LFB_CONTAINER_BACKEND=docker\n" in exported
        daemon_values = daemon_environment.read_text(encoding="utf-8")
        assert "AWS_SECRET_ACCESS_KEY" not in daemon_values
        assert "OPENAI_API_KEY" not in daemon_values
        assert f"XDG_RUNTIME_DIR={runtime_directory}" in daemon_values
        installs = sudo_log.read_text(encoding="utf-8")
        assert "docker-ce-rootless-extras=5:28.0.4-1~ubuntu.24.04~noble" in installs
        assert "uidmap slirp4netns" in installs
        assert "lfb-docker-rootless" not in installs
    finally:
        if daemon_pid_path.exists():
            os.kill(int(daemon_pid_path.read_text(encoding="utf-8")), 15)


def test_fan_in_assembles_optional_transcripts_with_preserved_cell_ids(
    tmp_path: Path,
) -> None:
    inputs = tmp_path / "inputs"
    (inputs / "artifacts").mkdir(parents=True)
    for name in (
        "run-manifest.json",
        "forecast-release.json",
        "model-registry.json",
    ):
        (inputs / name).write_bytes(b"{}\n")
    (inputs / "artifacts" / "packet.json").write_bytes(b"packet\n")
    state_root = tmp_path / "state"
    state_root.mkdir()
    identity = {
        "run_identity_sha256": "1" * 64,
        "forecast_release_digest": "2" * 64,
        "model_registry_sha256": "3" * 64,
        "model_key": "openai:gpt-5.6-luna",
    }
    transcript = b'{ "messages": [{"type":"tool_result","output":"docs"}] }\n'

    def write_state(
        name: str,
        cell_id: str,
        receipt_name: str | None,
        transcript_bytes: bytes | None = None,
        status: str = "completed",
    ) -> None:
        state = state_root / name
        state.mkdir(parents=True)
        if receipt_name is not None:
            (state / "receipts").mkdir()
        (state / "state.json").write_text(
            json.dumps({"cell_id": cell_id, "status": status}) + "\n",
            encoding="utf-8",
        )
        (state / "failure-summary.json").write_text(
            json.dumps({"status": status}) + "\n", encoding="utf-8"
        )
        if receipt_name is not None:
            receipt = {
                **identity,
                "cell_id": cell_id,
                "case_id": f"case-{name}",
                "unit_id": f"unit-{name}",
                "required_unit_ids": [f"unit-{name}"],
                "repeat_index": 1,
                "parser_output": {"probability_fully_dismissed": 0.5},
            }
            (state / "receipts" / receipt_name).write_text(
                json.dumps(receipt) + "\n", encoding="utf-8"
            )
        if transcript_bytes is not None:
            (state / "transcripts").mkdir()
            (state / "transcripts" / f"{cell_id}.json").write_bytes(transcript_bytes)

    write_state("cell-a-state", "cell-a", "receipt-a.json", transcript)
    # An older cell artifact can be complete without a transcript directory.
    write_state("cell-b-state", "cell-b", "receipt-b.json")
    # A failed cell may have a transcript even when no receipt was produced.
    write_state(
        "cell-failed-state",
        "cell-failed",
        None,
        b'{"messages":[{"type":"tool_result"}]}\n',
        status="failed",
    )

    section = WORKFLOW[
        WORKFLOW.index(
            "      - name: Assemble exact protected fan-in source artifact"
        ) :
    ]
    script = textwrap.dedent(
        section.split("python - <<'PY'\n", 1)[1].split("          PY", 1)[0]
    )
    output = tmp_path / "output"
    script = (
        script.replace('Path("/tmp/lfb-forecast-inputs")', f"Path({str(inputs)!r})")
        .replace('Path("/tmp/lfb-state-artifacts")', f"Path({str(state_root)!r})")
        .replace('Path("/tmp/lfb-forecast-results")', f"Path({str(output)!r})")
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env={
            **os.environ,
            "RELEASE_SHA": "a" * 40,
            "MANIFEST_URI": "manifests/cycle-1/run-manifest.json",
            "FORECAST_RELEASE_URI": "manifests/cycle-1/forecast-release.json",
            "ARTIFACT_ROOT_URI": "s3://results/cycle-1/artifacts/",
            "MODEL_REGISTRY_URI": "model_registries/openai.json",
            "MODEL_KEY": "openai:gpt-5.6-luna",
            "REPEAT_COUNT": "1",
            "CEILING_MICROUSD": "100000000",
            "ACCOUNT": "default",
            "GITHUB_RUN_ID": "123",
            "GITHUB_RUN_ATTEMPT": "1",
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert (output / "transcripts" / "cell-a.json").read_bytes() == transcript
    assert (output / "transcripts" / "cell-failed.json").read_bytes() == (
        b'{"messages":[{"type":"tool_result"}]}\n'
    )
    assert not (output / "transcripts" / "cell-b.json").exists()


def test_fan_in_refuses_conflicting_transcript_destinations(
    tmp_path: Path,
) -> None:
    inputs = tmp_path / "inputs"
    (inputs / "artifacts").mkdir(parents=True)
    for name in (
        "run-manifest.json",
        "forecast-release.json",
        "model-registry.json",
    ):
        (inputs / name).write_bytes(b"{}\n")
    (inputs / "artifacts" / "packet.json").write_bytes(b"packet\n")
    state_root = tmp_path / "state"
    state_root.mkdir()
    identity = {
        "run_identity_sha256": "1" * 64,
        "forecast_release_digest": "2" * 64,
        "model_registry_sha256": "3" * 64,
        "model_key": "openai:gpt-5.6-luna",
    }
    for name, transcript in (("first", b"first"), ("second", b"second")):
        state = state_root / name
        (state / "receipts").mkdir(parents=True)
        (state / "state.json").write_text(
            json.dumps({"cell_id": "same-cell", "status": "completed"}) + "\n",
            encoding="utf-8",
        )
        (state / "failure-summary.json").write_text(
            json.dumps({"status": "completed"}) + "\n", encoding="utf-8"
        )
        receipt = {
            **identity,
            "cell_id": "same-cell",
            "case_id": f"case-{name}",
            "unit_id": f"unit-{name}",
            "required_unit_ids": [f"unit-{name}"],
            "repeat_index": 1,
            "parser_output": {"probability_fully_dismissed": 0.5},
        }
        (state / "receipts" / f"{name}.json").write_text(
            json.dumps(receipt) + "\n", encoding="utf-8"
        )
        (state / "transcripts").mkdir()
        (state / "transcripts" / "same-cell.json").write_bytes(transcript)

    section = WORKFLOW[
        WORKFLOW.index(
            "      - name: Assemble exact protected fan-in source artifact"
        ) :
    ]
    script = textwrap.dedent(
        section.split("python - <<'PY'\n", 1)[1].split("          PY", 1)[0]
    )
    output = tmp_path / "output"
    script = (
        script.replace('Path("/tmp/lfb-forecast-inputs")', f"Path({str(inputs)!r})")
        .replace('Path("/tmp/lfb-state-artifacts")', f"Path({str(state_root)!r})")
        .replace('Path("/tmp/lfb-forecast-results")', f"Path({str(output)!r})")
    )
    failed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env={
            **os.environ,
            "RELEASE_SHA": "a" * 40,
            "MANIFEST_URI": "manifests/cycle-1/run-manifest.json",
            "FORECAST_RELEASE_URI": "manifests/cycle-1/forecast-release.json",
            "ARTIFACT_ROOT_URI": "s3://results/cycle-1/artifacts/",
            "MODEL_REGISTRY_URI": "model_registries/openai.json",
            "MODEL_KEY": "openai:gpt-5.6-luna",
            "REPEAT_COUNT": "1",
            "GITHUB_RUN_ID": "123",
            "GITHUB_RUN_ATTEMPT": "1",
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert failed.returncode != 0
    assert "duplicate durable transcript destination" in failed.stderr
