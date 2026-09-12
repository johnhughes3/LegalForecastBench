from __future__ import annotations

import importlib.util
import io
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from zipfile import ZipFile

import pytest
from legalforecast.contracts import (
    ARTIFACT_CANONICAL_JSON_V1,
    ARTIFACT_RAW_SHA256_V1,
    PUBLIC_RUN_IDENTITY_V1,
)
from legalforecast.runner.ledger import RunnerLedger
from legalforecast.runner.protected_recovery import RecoveryCell

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github/scripts/protected-benchmark-recovery.py"
_spec = importlib.util.spec_from_file_location("protected_benchmark_recovery", SCRIPT)
assert _spec is not None and _spec.loader is not None
_recovery = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_recovery)

MODEL_KEY = "openai:gpt-test"
REGISTRY_DIGEST = "a" * 64
ENTRY_DIGEST = "b" * 64
RELEASE_DIGEST = "c" * 64
ACCOUNT = "official"
CEILING = 10_000_000


def test_materialize_expands_bundle_and_exposes_missing_cell_to_loader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def archive(members: dict[str, bytes]) -> bytes:
        output = io.BytesIO()
        with ZipFile(output, "w") as zipped:
            for name, payload in members.items():
                zipped.writestr(name, payload)
        return output.getvalue()

    identity = _identity()
    carried_id, missing_id = "a" * 64, "b" * 64
    source = _state(
        tmp_path / "source", cell_id=carried_id, attempt=1, identity=identity
    )
    original = {path.name: path.read_bytes() for path in source.iterdir()}
    payloads = {
        1: archive(
            {
                "expected-cells.json": json.dumps(
                    [
                        {"cell_id": carried_id, "repeat_index": 1},
                        {"cell_id": missing_id, "repeat_index": 1},
                    ]
                ).encode()
            }
        ),
        2: archive({f"{carried_id}.zip": archive(original)}),
    }

    class Client:
        def download_artifact(self, repo: str, artifact_id: int) -> bytes:
            assert repo == "owner/bench"
            return payloads[artifact_id]

    monkeypatch.setattr(_recovery, "GhRecoveryClient", Client)
    workspace = tmp_path / "materialized"
    _recovery._materialize(
        {
            "repo": "owner/bench",
            "source": {
                "locked_inputs_artifact": {"id": 1},
                "state_artifacts": [
                    {"id": 2, "name": "restored-forecast-state-123-attempt-1"}
                ],
            },
        },
        workspace,
    )
    states = workspace / "states"
    carried = states / f"locked-run-state-restored-{carried_id}-attempt-1"
    assert {path.name: path.read_bytes() for path in carried.iterdir()} == original
    cells = {cell.cell_id: cell for cell in _load(states, identity_sha=identity[1])}
    assert set(cells) == {carried_id, missing_id}
    assert not cells[missing_id].completed
    assert cells[missing_id].local_attempt_id is None
    assert cells[missing_id].evidence_error is None


def _identity(*, marker: str = "") -> tuple[dict[str, object], str]:
    identity: dict[str, object] = {
        "schema_version": "legalforecast.public-run-identity.v1",
        "account": ACCOUNT,
        "ablation": "none",
        "model_registry_sha256": REGISTRY_DIGEST,
        "model_registry_entry_sha256": ENTRY_DIGEST,
        "served_model_version": "gpt-test",
        "marker": marker,
    }
    digest = str(
        ARTIFACT_RAW_SHA256_V1.commit(identity, domain=PUBLIC_RUN_IDENTITY_V1).digest
    )
    return identity, digest


def _state(
    root: Path,
    *,
    cell_id: str,
    attempt: int,
    status: str = "failed",
    identity: tuple[dict[str, object], str] | None = None,
    local_attempt_id: str | None = None,
    transcript: bytes | None = None,
) -> Path:
    directory = root / f"locked-run-state-{cell_id}-attempt-{attempt}"
    directory.mkdir(parents=True)
    (directory / "state.json").write_text(
        json.dumps({"cell_id": cell_id, "status": status, "repeat_index": 1}),
        encoding="utf-8",
    )
    if identity is not None:
        identity_record, identity_sha = identity
        ledger_path = directory / "ledger.sqlite3"
        with RunnerLedger(ledger_path, state_only_provider_attempts=True) as ledger:
            ledger.ensure_run(
                identity_sha256=identity_sha,
                identity_json=ARTIFACT_CANONICAL_JSON_V1.encode(
                    identity_record
                ).decode(),
                release_digest=RELEASE_DIGEST,
                harness="native",
                model_key=MODEL_KEY,
                ceiling_microusd=CEILING,
                approval_reference="",
            )
        if local_attempt_id is not None:
            with sqlite3.connect(ledger_path) as connection:
                connection.execute(
                    """
                    INSERT INTO public_runner_cells(
                        cell_id, run_identity_sha256, case_id, unit_id,
                        required_unit_ids_json, repeat_index, status,
                        provider_attempt_id
                    ) VALUES (?, ?, 'case', 'unit', '[\"unit\"]', 1, 'reserved', ?)
                    """,
                    (cell_id, identity_sha, local_attempt_id),
                )
    if transcript is not None:
        transcripts = directory / "transcripts"
        transcripts.mkdir()
        (transcripts / f"{cell_id}.json").write_bytes(transcript)
    return directory


def _load(state_root: Path, *, identity_sha: str) -> tuple[RecoveryCell, ...]:
    return cast(
        tuple[RecoveryCell, ...],
        _recovery._load_cells(
            state_root,
            registry_path=state_root / "model-registry.json",
            registry_digest=REGISTRY_DIGEST,
            registry_entry_digest=ENTRY_DIGEST,
            entry=object(),
            run_identity_sha256=identity_sha,
            model_key=MODEL_KEY,
            account=ACCOUNT,
            ceiling=CEILING,
            release_digest=RELEASE_DIGEST,
        ),
    )


def test_missing_ledger_and_partial_transcript_remain_retryable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    identity = _identity()
    _state(tmp_path, cell_id="sibling", attempt=1, identity=identity)
    _state(tmp_path, cell_id="pretransport", attempt=2)
    _state(
        tmp_path,
        cell_id="partial",
        attempt=2,
        identity=identity,
        local_attempt_id="local-partial-attempt",
        transcript=b'{"messages": [',
    )

    def reject_partial(*_args: object, **_kwargs: object) -> None:
        raise ValueError("partial")

    monkeypatch.setattr(_recovery, "managed_result_from_transcript", reject_partial)

    cells = {cell.cell_id: cell for cell in _load(tmp_path, identity_sha=identity[1])}

    assert cells["pretransport"].evidence_error is None
    assert cells["pretransport"].local_attempt_id is None
    assert cells["partial"].evidence_error is None
    assert cells["partial"].terminal_response is None
    assert cells["partial"].local_attempt_id == "local-partial-attempt"


def test_mismatched_ledger_identity_blocks_only_that_cell(tmp_path: Path) -> None:
    identity = _identity()
    mismatched = _identity(marker="different")
    _state(tmp_path, cell_id="valid", attempt=2, identity=identity)
    _state(
        tmp_path,
        cell_id="mismatch",
        attempt=1,
        identity=mismatched,
        local_attempt_id="wrong-run-attempt",
    )

    cells = {cell.cell_id: cell for cell in _load(tmp_path, identity_sha=identity[1])}

    assert cells["valid"].evidence_error is None
    assert (
        cells["mismatch"].evidence_error == "cell ledger differs from frozen identity"
    )


def test_latest_setup_failure_prefers_older_valid_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    identity = _identity()
    _state(tmp_path, cell_id="cell", attempt=2)
    _state(
        tmp_path,
        cell_id="cell",
        attempt=1,
        identity=identity,
        local_attempt_id="older-local-attempt",
        transcript=b'{"terminal": true}',
    )
    result = SimpleNamespace(
        input_tokens=10,
        output_tokens=5,
        raw_output='{"forecast":"preserved"}',
    )

    def recover_terminal(*_args: object, **_kwargs: object) -> SimpleNamespace:
        return result

    monkeypatch.setattr(_recovery, "managed_result_from_transcript", recover_terminal)
    from legalforecast.runner import managed_execution

    def terminal_cost(*_args: object, **_kwargs: object) -> float:
        return 0.1

    monkeypatch.setattr(managed_execution, "_managed_result_cost", terminal_cost)

    (cell,) = _load(tmp_path, identity_sha=identity[1])

    assert cell.local_attempt_id == "older-local-attempt"
    assert cell.terminal_response is not None
    assert cell.evidence_error is None


@pytest.mark.parametrize("malformed", [False, True])
def test_invalid_terminal_transcript_blocks_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, malformed: bool
) -> None:
    identity = _identity()
    raw = (
        b'{"agent_status":"failed","messages":[{"kind":"response","parts":['
        b'{"part_kind":"tool-call","tool_name":"final_result"}]}]}'
    )
    _state(
        tmp_path,
        cell_id="terminal",
        attempt=1,
        identity=identity,
        local_attempt_id="original-attempt",
        transcript=raw[:-2] if malformed else raw,
    )

    def reject_terminal(*_args: object, **_kwargs: object) -> None:
        raise ValueError("invalid final output")

    monkeypatch.setattr(_recovery, "managed_result_from_transcript", reject_terminal)
    (cell,) = _load(tmp_path, identity_sha=identity[1])
    assert cell.evidence_error is not None
    assert "terminal transcript requires repair" in cell.evidence_error


@pytest.mark.parametrize("valid", [True, False])
def test_completed_cell_requires_valid_predictions(tmp_path: Path, valid: bool) -> None:
    from legalforecast.evals.output_parser import (
        parse_model_output,
        public_parser_record,
    )

    identity = _identity()
    directory = _state(
        tmp_path,
        cell_id="candidate",
        attempt=1,
        status="completed",
        identity=identity,
        local_attempt_id="paid-attempt",
    )
    raw = (
        json.dumps(
            {
                "case_assessment": "Fixture",
                "predictions": [
                    {"unit_id": "unit", "probability_fully_dismissed": 0.5}
                ],
            }
        )
        if valid
        else "A prose response without predictions."
    )
    receipt = json.dumps(
        {
            "parser_output": public_parser_record(
                parse_model_output(raw, required_unit_ids=("unit",))
            )
        }
    ).encode()
    with sqlite3.connect(directory / "ledger.sqlite3") as connection:
        connection.execute(
            "UPDATE public_runner_cells SET status='completed', receipt_payload=?",
            (receipt,),
        )
    cell = _load(tmp_path, identity_sha=identity[1])[0]
    assert cell.completed is valid
    if valid:
        assert cell.evidence_error is None
    else:
        assert cell.evidence_error is not None
        assert "invalid or defaulted" in cell.evidence_error
