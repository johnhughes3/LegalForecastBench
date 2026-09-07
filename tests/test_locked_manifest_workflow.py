from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import sys
import textwrap
import threading
import time
import types
from pathlib import Path

import pytest
from legalforecast.release import ForecastRelease, issue_synthetic_release

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github/workflows/run-benchmark.yaml"
LEGACY_WORKFLOW_PATH = ROOT / ".github/workflows/run-benchmark-manifest.yaml"
WORKFLOW = WORKFLOW_PATH.read_text(encoding="utf-8")


def test_workflow_loads_serialized_release_through_json_validation(
    tmp_path: Path,
) -> None:
    issue_synthetic_release(tmp_path / "release")
    release_path = tmp_path / "release" / "forecast-release.json"
    expressions = re.findall(
        r"^          (?:release|forecast) = (ForecastRelease\..+)$",
        WORKFLOW,
        re.MULTILINE,
    )
    assert len(expressions) == 2
    for expression in expressions:
        # Run the actual workflow expressions over an issued JSON artifact.
        def path_loader(_: object) -> Path:
            return release_path

        loaded = eval(
            compile(ast.parse(expression, mode="eval"), "workflow-loader", "eval"),
            {
                "ForecastRelease": ForecastRelease,
                "release_path": release_path,
                "Path": path_loader,
                "json": json,
            },
        )
        assert isinstance(loaded, ForecastRelease)
        assert len(loaded.cases) == 3
        assert len(loaded.prediction_units) == 3


def test_concurrency_group_remains_bounded_for_long_release_locators() -> None:
    section = WORKFLOW.split("\nconcurrency:\n", 1)[1].split("\njobs:", 1)[0]
    group = re.search(r"^  group: (.+)$", section, re.MULTILINE)
    assert group is not None
    assert "${{" not in group.group(1)
    assert 0 < len(group.group(1)) < 400
    assert "cancel-in-progress: false" in section


def _job(name: str, next_name: str | None = None) -> str:
    start = WORKFLOW.index(f"  {name}:")
    end = WORKFLOW.index(f"  {next_name}:", start) if next_name else len(WORKFLOW)
    return WORKFLOW[start:end]


def test_one_canonical_workflow_uses_locked_outcome_blinded_inputs() -> None:
    assert WORKFLOW_PATH.is_file()
    assert not LEGACY_WORKFLOW_PATH.exists()
    for input_name in (
        "manifest_uri:",
        "forecast_release_uri:",
        "artifact_root_uri:",
        "model_registry_uri:",
        "model_key:",
        "ceiling_microusd:",
        "repeat_count:",
    ):
        assert f"      {input_name}" in WORKFLOW
    assert "labels_release_uri" not in WORKFLOW
    assert "run_input_manifest_uri:" not in WORKFLOW
    assert "labels_uri:" not in WORKFLOW
    assert "run-benchmark-manifest.yaml" not in WORKFLOW


def test_prepare_materializes_only_forecast_release_declared_artifacts() -> None:
    prepare = _job("prepare-inputs", "run-openai")
    assert "environment: legalforecastbench-official-eval-prepare-inputs" in prepare
    assert "LFB_GITHUB_PREPARE_INPUTS_ROLE_ARN" in prepare
    assert "LFB_AWS_REGION" in prepare
    assert "LFB_RESULTS_BUCKET" in prepare
    assert "ForecastRelease.model_validate" in prepare
    assert "declared: dict[str, tuple[str, int]]" in prepare
    assert "load_forecast_execution" in prepare
    assert "actual != set(declared)" in prepare
    assert "aws s3 sync" not in prepare
    assert "uv run --with boto3 python" in prepare
    assert "from concurrent.futures import ThreadPoolExecutor" in prepare
    assert 's3_client = boto3.client("s3")' in prepare
    assert "s3_client.get_object(Bucket=bucket, Key=key)" in prepare
    assert "ThreadPoolExecutor(max_workers=min(16, len(items)))" in prepare
    assert 'subprocess.run(["aws", "s3", "cp"' not in prepare
    assert "fetch_tree" not in prepare
    assert "cp -a" not in prepare
    assert "labels" not in prepare.lower()
    assert "Build dynamic logical-cell matrices" in prepare
    assert "model_registry" in prepare
    assert '"cell_id"' in prepare
    assert '"unit_id"' in prepare
    assert '"repeat_index"' in prepare
    assert '"ablation"' in prepare


def _prepare_inline_script() -> str:
    prepare = _job("prepare-inputs", "run-openai")
    marker = "          uv run --with boto3 python - <<'PY'\n"
    body_start = prepare.index(marker) + len(marker)
    body_end = prepare.index("          PY\n", body_start)
    return textwrap.dedent(prepare[body_start:body_end])


class _FakeS3Body:
    def __init__(self, payload: bytes, client: _FakeS3Client) -> None:
        self._payload = payload
        self._client = client

    def read(self) -> bytes:
        with self._client.lock:
            self._client.active_reads += 1
            self._client.max_active_reads = max(
                self._client.max_active_reads, self._client.active_reads
            )
        try:
            time.sleep(0.005)
            return self._payload
        finally:
            with self._client.lock:
                self._client.active_reads -= 1

    def close(self) -> None:
        with self._client.lock:
            self._client.closed_bodies += 1


class _FakeS3Client:
    def __init__(self, source_root: Path, corrupt_relative: str | None) -> None:
        self._source_root = source_root
        self._corrupt_relative = corrupt_relative
        self.lock = threading.Lock()
        self.active_reads = 0
        self.max_active_reads = 0
        self.closed_bodies = 0
        self.requested_keys: list[tuple[str, str]] = []

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, _FakeS3Body]:
        relative = Key.removeprefix("prefix/")
        payload = (
            b"corrupted declared artifact\n"
            if relative == self._corrupt_relative
            else (self._source_root / relative).read_bytes()
        )
        with self.lock:
            self.requested_keys.append((Bucket, Key))
        return {"Body": _FakeS3Body(payload, self)}


def _run_prepare_inline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    run_name: str,
    corrupt_relative: str | None,
) -> tuple[Path, _FakeS3Client, set[str]]:
    source_root = tmp_path / run_name / "source"
    issue_synthetic_release(source_root)
    release = ForecastRelease.model_validate_json(
        (source_root / "forecast-release.json").read_bytes()
    )
    declared = {
        *(document.path for case in release.cases for document in case.documents),
        *(unit.packet_path for unit in release.prediction_units),
        *(unit.prompt_path for unit in release.prediction_units),
    }
    locked_root = tmp_path / run_name / "locked"
    (locked_root / "artifacts").mkdir(parents=True)
    shutil.copyfile(
        source_root / "forecast-release.json", locked_root / "forecast-release.json"
    )
    client = _FakeS3Client(source_root, corrupt_relative)
    fake_boto3 = types.ModuleType("boto3")

    def client_factory(service: str) -> _FakeS3Client:
        assert service == "s3"
        return client

    fake_boto3.__dict__["client"] = client_factory
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
    monkeypatch.setenv("LFB_ARTIFACT_ROOT_URI", "s3://bucket/prefix")
    rendered = _prepare_inline_script().replace(
        'Path("/tmp/lfb-locked-inputs")', f"Path({str(locked_root)!r})"
    )
    exec(compile(rendered, "run-benchmark-prepare", "exec"), {})
    return locked_root, client, declared


def test_prepare_s3_downloader_reuses_client_and_refuses_corruption(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    locked_root, client, declared = _run_prepare_inline(
        tmp_path, monkeypatch, run_name="success", corrupt_relative=None
    )
    assert client.max_active_reads > 1
    assert len(client.requested_keys) == len(declared)
    assert client.closed_bodies == len(client.requested_keys)
    assert {key.removeprefix("prefix/") for _, key in client.requested_keys} == declared
    actual = {
        path.relative_to(locked_root / "artifacts").as_posix()
        for path in (locked_root / "artifacts").rglob("*")
        if path.is_file()
    }
    assert actual == declared

    with pytest.raises(SystemExit, match="declared artifact commitment mismatch"):
        _run_prepare_inline(
            tmp_path,
            monkeypatch,
            run_name="corrupt",
            corrupt_relative=sorted(declared)[0],
        )


def test_prepare_exports_real_provider_matrices_from_registry_and_release() -> None:
    prepare = _job("prepare-inputs", "run-openai")
    for provider in ("openai", "anthropic", "gemini"):
        assert (
            f"{provider}_matrix: ${{{{ steps.matrix.outputs.{provider}_matrix }}}}"
            in prepare
        )
        assert (
            f"{provider}_count: ${{{{ steps.matrix.outputs.{provider}_count }}}}"
            in prepare
        )
    assert 'print(f"{provider}_matrix=' in prepare
    assert (
        "matrix: ${{ fromJSON(needs.prepare-inputs.outputs.openai_matrix) }}"
        in WORKFLOW
    )
    assert (
        "matrix: ${{ fromJSON(needs.prepare-inputs.outputs.anthropic_matrix) }}"
        in WORKFLOW
    )
    assert (
        "matrix: ${{ fromJSON(needs.prepare-inputs.outputs.gemini_matrix) }}"
        in WORKFLOW
    )
    assert "cell: [run]" not in WORKFLOW
    assert "model_key" in prepare
    assert "prediction_units" in prepare
    assert "derive_cell_id" in prepare
    assert "derive_run_identity_sha256" in prepare


def test_provider_jobs_are_secret_isolated_and_outcome_blinded() -> None:
    jobs = {
        "openai": _job("run-openai", "run-anthropic"),
        "anthropic": _job("run-anthropic", "run-gemini"),
        "gemini": _job("run-gemini"),
    }
    secrets = {
        "openai": "secrets.OPENAI_API_KEY",
        "anthropic": "secrets.ANTHROPIC_API_KEY",
        "gemini": "secrets.GEMINI_API_KEY",
    }
    forbidden_secrets = {
        "openai": ("secrets.ANTHROPIC_API_KEY", "secrets.GEMINI_API_KEY"),
        "anthropic": ("secrets.OPENAI_API_KEY", "secrets.GEMINI_API_KEY"),
        "gemini": ("secrets.OPENAI_API_KEY", "secrets.ANTHROPIC_API_KEY"),
    }
    for provider, job in jobs.items():
        assert job.count(secrets[provider]) == 1
        assert all(secret not in job for secret in forbidden_secrets[provider])
        assert "labels_release_uri" not in job
        assert "LABELS" not in job
        assert "--labels" not in job
        assert "--approval-reference" not in job
        assert "GITHUB_EVENT_PATH" not in job
        assert "cell_id" in job
        assert "unit_id" in job
        assert "repeat_index" in job
        assert "ablation" in job
        assert "if: ${{ always() }}" in job
        assert "ledger.sqlite3" in job
        assert "receipts" in job
        assert "if-no-files-found: error" in job
        assert "actions: read" in job
        assert "id-token: write" in job
        assert "PROVIDER_AUTHORITY_TABLE" in job
        assert (
            "max-parallel: ${{ fromJSON(needs.prepare-inputs.outputs.max_parallel) }}"
            in job
        )


def test_provider_role_session_names_fit_sts_limit_with_long_cell_slug() -> None:
    long_cell_id_slug = "c" * 64
    assert len(long_cell_id_slug) == 64
    rendered_run_id = "9" * 20
    rendered_job_index = "31"
    for name, next_name in (
        ("run-openai", "run-anthropic"),
        ("run-anthropic", "run-gemini"),
        ("run-gemini", None),
    ):
        job = _job(name, next_name)
        match = re.search(r"^          role-session-name: (.+)$", job, re.MULTILINE)
        assert match is not None
        session_name = (
            match.group(1)
            .replace("${{ github.run_id }}", rendered_run_id)
            .replace("${{ strategy.job-index }}", rendered_job_index)
            .replace("${{ matrix.cell_id_slug }}", long_cell_id_slug)
        )
        assert len(session_name) <= 64
        assert "matrix.cell_id_slug" not in match.group(1)


def test_provider_jobs_execute_one_exact_cell_and_do_not_score() -> None:
    for name, next_name in (
        ("run-openai", "run-anthropic"),
        ("run-anthropic", "run-gemini"),
        ("run-gemini", None),
    ):
        job = _job(name, next_name)
        assert '--cell-id "${CELL_ID}"' in job
        assert '--unit-id "${UNIT_ID}"' in job
        assert '--repeat-index "${REPEAT_INDEX}"' in job
        assert '--ablation "${ABLATION}"' in job
        assert "score" not in job.lower()
        assert "report" not in job.lower()
    assert "score-and-report:" not in WORKFLOW
    assert "legalforecast score" not in WORKFLOW
    assert "legalforecast report" not in WORKFLOW


def test_source_identity_concurrency_and_budget_gates_are_fail_closed() -> None:
    assert "concurrency:" in WORKFLOW
    assert "inputs.manifest_uri" in WORKFLOW
    assert "inputs.forecast_release_uri" in WORKFLOW
    assert "inputs.ceiling_microusd" in WORKFLOW
    assert "cancel-in-progress: false" in WORKFLOW
    next_jobs = {
        "prepare-inputs": "run-openai",
        "run-openai": "run-anthropic",
        "run-anthropic": "run-gemini",
        "run-gemini": None,
    }
    for job_name, next_name in next_jobs.items():
        job = _job(job_name, next_name)
        # origin/main must be resolvable here, but not via a separate `git
        # fetch`: persist-credentials: false on the checkout step leaves no
        # token for a later step, so a bare fetch dies with "could not read
        # Username for 'https://github.com'" (legalforecastbench-2x9o).
        # fetch-depth: 0 makes the checkout itself fetch full history and
        # refs, including origin/main, under its own credentials.
        assert "fetch-depth: 0" in job
        assert "persist-credentials: false" in job
        assert "git fetch --no-tags --depth=1 origin main" not in job
        assert "git merge-base --is-ancestor HEAD origin/main" in job
        assert "git rev-parse HEAD" in job
    assert "CEILING_MICROUSD" in _job("prepare-inputs", "run-openai")
    assert '[[ "${CEILING_MICROUSD}" =~ ^[1-9][0-9]*$ ]]' in WORKFLOW
    assert '"max_parallel must be between 1 and 32"' in WORKFLOW
    assert (
        "repeat_count must be exactly 1 until repeated-sampling fan-in is supported"
        in WORKFLOW
    )


def _source_check_script() -> str:
    marker = "      - name: Require an exact main-reachable source revision\n"
    start = WORKFLOW.index(marker)
    body_start = WORKFLOW.index("        run: |\n", start) + len("        run: |\n")
    body_end = WORKFLOW.index("      - name:", body_start)
    return textwrap.dedent(WORKFLOW[body_start:body_end])


def test_source_check_executes_main_ancestry_over_a_git_graph(tmp_path: Path) -> None:
    """Accept an older main commit and reject a same-root unmerged commit."""

    repository = tmp_path / "repository"
    subprocess.run(["git", "init", "--quiet", str(repository)], check=True)

    def git(*args: str) -> str:
        completed = subprocess.run(
            ["git", "-C", str(repository), *args],
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()

    git("config", "user.name", "workflow-test")
    git("config", "user.email", "workflow-test@example.invalid")
    (repository / "history.txt").write_text("root\n", encoding="utf-8")
    git("add", "history.txt")
    git("commit", "--quiet", "-m", "root")
    root = git("rev-parse", "HEAD")
    git("branch", "--move", "main")

    (repository / "history.txt").write_text("past\n", encoding="utf-8")
    git("commit", "--quiet", "-am", "past main commit")
    past = git("rev-parse", "HEAD")
    (repository / "history.txt").write_text("current\n", encoding="utf-8")
    git("commit", "--quiet", "-am", "current main commit")
    main = git("rev-parse", "HEAD")

    git("checkout", "--quiet", "--detach", root)
    (repository / "unmerged.txt").write_text("unmerged\n", encoding="utf-8")
    git("add", "unmerged.txt")
    git("commit", "--quiet", "-m", "unmerged branch commit")
    unmerged = git("rev-parse", "HEAD")
    git("update-ref", "refs/remotes/origin/main", main)

    script = _source_check_script()

    def run_source_check(head: str) -> subprocess.CompletedProcess[str]:
        git("checkout", "--quiet", "--detach", head)
        return subprocess.run(
            ["bash", "-c", script],
            cwd=repository,
            env={"RELEASE_SHA": head},
            capture_output=True,
            text=True,
        )

    valid = run_source_check(past)
    assert valid.returncode == 0, valid.stderr

    invalid = run_source_check(unmerged)
    assert invalid.returncode != 0


def test_prepare_rejects_repeats_before_any_provider_matrix() -> None:
    prepare = _job("prepare-inputs", "run-openai")
    validate_start = prepare.index("Validate dispatch identity and bounded values")
    matrix_start = prepare.index("Build dynamic logical-cell matrices")
    assert validate_start < matrix_start
    validate = prepare[validate_start:matrix_start]
    matrix = prepare[matrix_start:]
    reject_message = (
        "repeat_count must be exactly 1 until repeated-sampling fan-in is supported"
    )
    assert '[[ "${REPEAT_COUNT}" == "1" ]]' in validate
    assert reject_message in validate
    assert '[[ "${PROVIDER}" == "openai" ]]' not in validate
    assert "if repeat_count != 1:" in matrix
    assert reject_message in matrix
    assert (
        'if [[ "${PROVIDER}" == "openai" ]] && (( REPEAT_COUNT > 1 ))' not in WORKFLOW
    )
    assert "OpenAI repeat samples are not supported" not in WORKFLOW


def test_restore_is_attempt_qualified_and_fail_closed() -> None:
    assert "GITHUB_RUN_ATTEMPT" in WORKFLOW
    assert (
        "locked-run-state-${{ matrix.provider }}-${{ matrix.cell_id_slug }}-"
        "attempt-${{ github.run_attempt }}" in WORKFLOW
    )
    assert "newest prior valid attempt" in WORKFLOW
    assert (
        "all prior state artifacts were corrupt; refusing a fresh duplicate call"
        in WORKFLOW
    )
    assert "gh api --paginate --slurp" in WORKFLOW
    assert (
        "prior state download/API failure; refusing a fresh duplicate call" in WORKFLOW
    )
    assert "if status != 0:" in WORKFLOW
    assert "CREATE TABLE runs(status TEXT NOT NULL)" in WORKFLOW
    assert "if-no-files-found: error" in WORKFLOW
    assert "continue-on-error" not in WORKFLOW
    assert "path: /tmp/lfb-run\n" not in WORKFLOW
    assert "/tmp/lfb-run/failure-summary.json" in WORKFLOW


def test_combined_forecast_result_matches_protected_fan_in_contract() -> None:
    combined = _job("persist-forecast-results")
    assert "needs: [prepare-inputs, run-openai, run-anthropic, run-gemini]" in combined
    assert "if: ${{ always() && needs.prepare-inputs.result == 'success' }}" in combined
    assert (
        "name: official-forecast-results-${{ github.run_id }}-${{ github.run_attempt }}"
        in combined
    )
    assert (
        "name: locked-forecast-inputs-${{ github.run_id }}-attempt-"
        "${{ github.run_attempt }}" in WORKFLOW
    )
    for path in (
        "forecast-run.json",
        "run-manifest.json",
        "forecast-release.json",
        "model-registry.json",
        "run-summary.json",
        "ledger/ledger.sqlite3",
        "receipts",
        "artifacts",
    ):
        assert f"/tmp/lfb-forecast-results/{path}" in combined
    assert "if-no-files-found: error" in combined
    assert "receipts/*.json" in combined or 'glob("*.json")' in combined
    assert "labels" not in combined.lower()
    assert "score" not in combined.lower()
    assert "report" not in combined.lower()


def test_workflow_actions_are_immutable_sha_pins() -> None:
    references = re.findall(
        r"^\s*uses:\s+([^@\s]+)@([^\s#]+)", WORKFLOW, flags=re.MULTILINE
    )
    assert references
    assert all(re.fullmatch(r"[0-9a-f]{40}", revision) for _, revision in references)
    assert all("#" in line for line in WORKFLOW.splitlines() if "uses:" in line)


def test_workflow_does_not_fabricate_approval_references() -> None:
    assert "approval-reference" not in WORKFLOW
    assert "workflow-run-" not in WORKFLOW
