from __future__ import annotations

import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/prepare-jev-summaries.yaml").read_text(
    encoding="utf-8"
)


def test_jev_workflow_is_manual_bounded_and_uses_the_protected_environment() -> None:
    assert WORKFLOW.startswith("name: Prepare Jev Summaries\n")
    assert "workflow_dispatch:" in WORKFLOW
    assert "push:" not in WORKFLOW
    assert "pull_request:" not in WORKFLOW
    assert "timeout-minutes: 360" in WORKFLOW
    assert "environment: legalforecastbench-official-eval" in WORKFLOW
    assert "permissions:\n  actions: read\n  contents: read" in WORKFLOW
    assert "id-token:" not in WORKFLOW
    assert "run: uv sync --locked" in WORKFLOW


def test_jev_workflow_requires_exact_cross_run_artifact_identity() -> None:
    for input_name in (
        "source_run_id:",
        "locked_inputs_artifact_id:",
        "prior_summary_run_id:",
        "prior_summary_artifact_id:",
    ):
        assert input_name in WORKFLOW
    assert (
        "uses: actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c"
        in WORKFLOW
    )
    assert WORKFLOW.count("github-token: ${{ github.token }}") == 2
    assert WORKFLOW.count("artifact-ids: ${{ inputs.locked_inputs_artifact_id }}") == 1
    assert WORKFLOW.count("run-id: ${{ inputs.source_run_id }}") == 1
    assert "run-id: ${{ inputs.prior_summary_run_id }}" in WORKFLOW
    assert "repository: ${{ github.repository }}" in WORKFLOW


def test_jev_workflow_checks_origin_main_and_allowlisted_locked_inputs() -> None:
    assert "ref: main" in WORKFLOW
    assert "persist-credentials: false" in WORKFLOW
    assert "git rev-parse origin/main" in WORKFLOW
    assert 'test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"' in WORKFLOW
    assert "path: /tmp/lfb-jev-inputs" in WORKFLOW
    assert "/tmp/lfb-jev-inputs/run-manifest.json" in WORKFLOW
    assert "/tmp/lfb-jev-inputs/forecast-release.json" in WORKFLOW
    assert "/tmp/lfb-jev-inputs/artifacts" in WORKFLOW
    assert '"expected-cells.json"' in WORKFLOW
    assert '"resume-dispatch.json"' in WORKFLOW
    assert "transcript" not in WORKFLOW.lower()
    assert "labels-release" not in WORKFLOW.lower()


def test_jev_workflow_runs_the_release_bound_prepare_and_registry_commands() -> None:
    assert "--manifest /tmp/lfb-jev-inputs/run-manifest.json" in WORKFLOW
    assert "--forecast /tmp/lfb-jev-inputs/forecast-release.json" in WORKFLOW
    assert "--artifact-root /tmp/lfb-jev-inputs/artifacts" in WORKFLOW
    assert '--summary-registry "$SUMMARY_REGISTRY"' in WORKFLOW
    assert WORKFLOW.count('--summary-model "$SUMMARY_MODEL"') == 2
    assert '--provider "$JEV_PROVIDER"' in WORKFLOW
    assert "--cache /tmp/lfb-jev-summary/jev-summaries.json" in WORKFLOW
    assert "--ledger /tmp/lfb-jev-summary/summary-spend.sqlite3" in WORKFLOW
    assert '--ceiling-microusd "$CEILING"' in WORKFLOW
    assert "uv run legalforecast jev registry" in WORKFLOW
    assert "--output /tmp/lfb-jev-summary/model-registry.json" in WORKFLOW


def test_jev_workflow_resumes_both_cache_and_sqlite_ledger() -> None:
    assert "/tmp/lfb-jev-prior/jev-summaries.json" in WORKFLOW
    assert "/tmp/lfb-jev-prior/summary-spend.sqlite3" in WORKFLOW
    assert "cp -f /tmp/lfb-jev-prior/jev-summaries.json" in WORKFLOW
    assert "cp -f /tmp/lfb-jev-prior/summary-spend.sqlite3" in WORKFLOW
    assert "if: ${{ inputs.prior_summary_artifact_id != '' }}" in WORKFLOW


def test_jev_workflow_restores_the_latest_prior_attempt_without_repolling() -> None:
    assert "gh api --paginate --slurp" in WORKFLOW
    assert "actions/runs/${CURRENT_RUN_ID}/artifacts?per_page=100" in WORKFLOW
    assert "jev-summary-cache-{re.escape(run_id)}-attempt-" in WORKFLOW
    assert "attempt >= int(current_attempt)" in WORKFLOW
    assert (
        "gh api \\\n"
        '            "/repos/${GITHUB_REPOSITORY}/actions/artifacts/${ARTIFACT_ID}/zip"'
        in WORKFLOW
    )
    assert '> "${archive}"' in WORKFLOW
    assert "actions/artifacts/${ARTIFACT_ID}/zip" in WORKFLOW
    assert "steps.discover-automatic-resume.outputs.found == 'true'" in WORKFLOW
    assert "set(names) != allowed" in WORKFLOW


def test_jev_workflow_uploads_resume_state_always_and_registry_only_on_success() -> (
    None
):
    assert "if: ${{ always() }}" in WORKFLOW
    assert "id: checkpoint-summary-ledger" in WORKFLOW
    assert "PRAGMA wal_checkpoint(TRUNCATE)" in WORKFLOW
    assert "int(result[0]) != 0" in WORKFLOW
    assert "steps.checkpoint-summary-ledger.outcome == 'success'" in WORKFLOW
    assert WORKFLOW.count("retention-days: 90") == 2
    cache_upload = WORKFLOW.index("name: jev-summary-cache-")
    registry_upload = WORKFLOW.index("name: jev-model-registry-")
    assert WORKFLOW.rfind("if: ${{ always() }}", 0, cache_upload) != -1
    assert WORKFLOW.rfind("if: ${{ success() }}", 0, registry_upload) != -1
    assert "/tmp/lfb-jev-summary/jev-summaries.json" in WORKFLOW[cache_upload:]
    assert "/tmp/lfb-jev-summary/summary-spend.sqlite3" in WORKFLOW[cache_upload:]
    assert "/tmp/lfb-jev-summary/model-registry.json" in WORKFLOW[registry_upload:]


def test_jev_workflow_scopes_credentials_to_selected_summarizer() -> None:
    step = WORKFLOW[
        WORKFLOW.index(
            "- name: Prepare release-bound document summaries"
        ) : WORKFLOW.index("- name: Verify complete prior cache")
    ]
    assert (
        "OPENAI_API_KEY: ${{ inputs.summary_model == 'luna' "
        "&& secrets.OPENAI_API_KEY || '' }}" in step
    )
    assert (
        "AI_GATEWAY_API_KEY: ${{ inputs.summary_model == 'grok' "
        "&& secrets.AI_GATEWAY_API_KEY || '' }}" in step
    )
    assert WORKFLOW.count("secrets.OPENAI_API_KEY") == 1
    assert WORKFLOW.count("secrets.AI_GATEWAY_API_KEY") == 1
    assert "ANTHROPIC_API_KEY" not in WORKFLOW
    assert "GEMINI_API_KEY" not in WORKFLOW
    assert "inputs.summary_registry_path || inputs.luna_registry_path" in WORKFLOW
    assert '"spacexai/grok-4.6" if os.environ["SUMMARY_MODEL"] == "grok"' in WORKFLOW


def test_checkpointed_wal_ledger_survives_main_file_only_upload(tmp_path: Path) -> None:
    database = tmp_path / "summary-spend.sqlite3"
    ready = tmp_path / "writer-ready"
    writer = subprocess.Popen(
        [
            sys.executable,
            "-c",
            """
import sqlite3
import sys
from pathlib import Path

connection = sqlite3.connect(sys.argv[1], isolation_level=None)
connection.execute('PRAGMA journal_mode=WAL')
connection.execute('CREATE TABLE committed (value TEXT NOT NULL)')
connection.execute("INSERT INTO committed VALUES ('survives')")
Path(sys.argv[2]).write_text('ready', encoding='utf-8')
signal = __import__('signal')
signal.pause()
""",
            str(database),
            str(ready),
        ],
        start_new_session=True,
    )
    try:
        deadline = time.monotonic() + 5.0
        while not ready.exists() and writer.poll() is None:
            if time.monotonic() >= deadline:
                raise AssertionError("WAL writer did not commit its test row")
            time.sleep(0.01)
        if not ready.exists():
            raise AssertionError(f"WAL writer exited unexpectedly: {writer.returncode}")

        before_checkpoint = tmp_path / "before-checkpoint.sqlite3"
        shutil.copy2(database, before_checkpoint)
        with sqlite3.connect(before_checkpoint) as connection:
            assert (
                connection.execute(
                    "SELECT name FROM sqlite_master WHERE name = 'committed'"
                ).fetchone()
                is None
            )

        writer.terminate()
        writer.wait(timeout=5.0)

        with sqlite3.connect(
            database, isolation_level=None, timeout=30.0
        ) as connection:
            result = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        assert result is not None
        assert result[0] == 0

        uploaded = tmp_path / "uploaded.sqlite3"
        shutil.copy2(database, uploaded)
        with sqlite3.connect(uploaded) as connection:
            assert connection.execute("SELECT value FROM committed").fetchone() == (
                "survives",
            )
    finally:
        if writer.poll() is None:
            writer.kill()
            writer.wait(timeout=5.0)
