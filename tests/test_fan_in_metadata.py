"""Execute the hosted fan-in validator against durable run metadata."""

import json
import sqlite3
import textwrap
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("extra", "accepted"),
    [
        ({}, True),
        ({"account": "default", "ceiling_microusd": 40_000_000}, True),
        ({"account": "default"}, False),
        ({"account": "default", "ceiling_microusd": True}, False),
        ({"account": "", "ceiling_microusd": 1}, False),
        ({"account": "default", "ceiling_microusd": 0}, False),
        ({"unexpected": 1}, False),
    ],
)
def test_complete_fan_in_metadata_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    extra: dict[str, object],
    accepted: bool,
) -> None:
    metadata = {
        "schema_version": "legalforecast.forecast-run.v1",
        "workflow_run_id": 123,
        "workflow_run_attempt": 1,
        "release_sha": "a" * 40,
        "manifest_uri": "manifest",
        "forecast_release_uri": "forecast",
        "artifact_root_uri": "artifacts/",
        "model_registry_uri": "registry",
        "model_key": "openai:test",
        "run_identity_sha256": "a" * 64,
        "forecast_release_digest": "b" * 64,
        "model_registry_sha256": "c" * 64,
        "repeat_count": 1,
        **extra,
    }
    for field in (
        "release_sha",
        "manifest_uri",
        "forecast_release_uri",
        "artifact_root_uri",
        "model_registry_uri",
        "model_key",
    ):
        monkeypatch.setenv(field.upper(), str(metadata[field]))
    monkeypatch.setenv("FORECAST_RUN_ID", "123")
    monkeypatch.setenv("FORECAST_RUN_ATTEMPT", "1")
    (tmp_path / "forecast-run.json").write_text(json.dumps(metadata))
    (tmp_path / "run-summary.json").write_text(
        json.dumps(
            {
                "run_identity_sha256": metadata["run_identity_sha256"],
                "status": "completed",
            }
        )
    )
    (tmp_path / "ledger").mkdir()
    with sqlite3.connect(tmp_path / "ledger/ledger.sqlite3") as connection:
        connection.execute("CREATE TABLE runs (status TEXT)")
        connection.execute("INSERT INTO runs VALUES ('completed')")
    (tmp_path / "receipts").mkdir()
    receipt = {
        key: metadata[key]
        for key in (
            "schema_version",
            "run_identity_sha256",
            "forecast_release_digest",
            "model_key",
            "model_registry_sha256",
        )
    }
    receipt.update(
        case_id="case",
        unit_id="unit",
        required_unit_ids=["unit"],
        repeat_index=1,
        parser_output={},
    )
    (tmp_path / "receipts/receipt.json").write_text(json.dumps(receipt))
    workflow = Path(".github/workflows/fan-in-publish.yaml").read_text()
    section = workflow.split(
        "- name: Validate run identity, model registry, and complete durable state", 1
    )[1]
    script = textwrap.dedent(
        section.split("python - <<'PY'\n", 1)[1].split("          PY", 1)[0]
    )
    output = tmp_path / "records.jsonl"
    script = script.replace("/tmp/lfb-forecast", str(tmp_path)).replace(
        "/tmp/lfb-run-records.jsonl", str(output)
    )
    if accepted:
        exec(compile(script, "fan-in-validator", "exec"), {})
        assert json.loads(output.read_text())["model_id"] == "openai:test"
    else:
        with pytest.raises(SystemExit, match=r"forecast-run\.json"):
            exec(compile(script, "fan-in-validator", "exec"), {})
