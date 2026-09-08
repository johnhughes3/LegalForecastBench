from __future__ import annotations

from pathlib import Path

WORKFLOW = (
    Path(__file__).resolve().parents[1] / ".github/workflows/run-benchmark.yaml"
).read_text(encoding="utf-8")


def _job(name: str, next_name: str | None = None) -> str:
    start = WORKFLOW.index(f"  {name}:")
    end = WORKFLOW.index(f"  {next_name}:", start) if next_name else len(WORKFLOW)
    return WORKFLOW[start:end]


def test_gateway_lane_is_partitioned_from_direct_provider_jobs() -> None:
    prepare = _job("prepare-inputs", "run-openai")
    assert (
        "^(openai|anthropic|gemini|google|vercel_ai_gateway):[^:[:space:]]+$" in prepare
    )
    job = _job("run-gateway")
    assert "name: Vercel AI Gateway resumable forecast cells" in job
    assert "startsWith(inputs.model_key, 'vercel_ai_gateway:')" in job
    assert "needs.prepare-inputs.outputs.gateway_count != '0'" in job
    assert "fromJSON(needs.prepare-inputs.outputs.gateway_matrix)" in job
    assert "Download outcome-blinded inputs" in job
    assert "Recover saved managed transcript for provider-free replay" in job
    assert "scripts/recover_managed_transcript.py" in job
    assert "Configure rootless Docker for document tools" in job
    assert "Build isolated document tool image" in job
    assert job.index("Recover saved managed transcript") < job.index(
        "Configure rootless Docker"
    )


def test_gateway_credential_is_scoped_to_the_execute_step() -> None:
    job = _job("run-gateway")
    assert job.count("secrets.AI_GATEWAY_API_KEY") == 1
    assert "secrets.OPENAI_API_KEY" not in job
    assert "secrets.ANTHROPIC_API_KEY" not in job
    assert "secrets.GEMINI_API_KEY" not in job
    execute = job[job.index("Execute exact Vercel AI Gateway forecast cell") :]
    assert "AI_GATEWAY_API_KEY: ${{ secrets.AI_GATEWAY_API_KEY }}" in execute
    assert "if: ${{ always() }}" in job
    assert "ledger.sqlite3" in job
    assert "receipts" in job
    assert "transcripts" in job


def test_gateway_lane_is_included_in_protected_fan_in() -> None:
    combined = _job("persist-forecast-results")
    assert (
        "needs: [prepare-inputs, run-openai, run-anthropic, run-gemini, run-gateway]"
        in combined
    )
    assert "if: ${{ always() && needs.prepare-inputs.result == 'success' }}" in combined
