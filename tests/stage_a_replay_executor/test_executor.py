"""Synthetic fake-provider coverage for the canonical Stage A executor.

Fixture authenticity: these replay specs are hand-authored test artifacts and
use the closed ``synthetic_fixture`` authorization mode. They are not derived
from Cycle 1 private evidence and never open a provider transport.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

import pytest
from legalforecast.cli_commands.stage_a_replay import register as register_cli
from legalforecast.contracts import ARTIFACT_CANONICAL_JSON_V1
from legalforecast.ingestion.candidate_scoped_stage_a_replay import (
    CandidateScopedStageARerunRequest,
    StageAStageOutcome,
)
from legalforecast.ingestion.stage_a_replay_executor import contract as contract_module
from legalforecast.ingestion.stage_a_replay_executor import executor as executor_module
from legalforecast.ingestion.stage_a_replay_executor import lineage as lineage_module
from legalforecast.ingestion.stage_a_replay_executor.executor import (
    StageAReplayExecutorError,
    execute_stage_a_replay,
    load_replay_spec,
)
from tests.stage_a_replay_executor.fixtures import (
    FakeSpendMeter as _FakeSpendMeter,
)
from tests.stage_a_replay_executor.fixtures import read_spec as _read_spec
from tests.stage_a_replay_executor.fixtures import (
    settled_reviewer as _settled_reviewer,
)
from tests.stage_a_replay_executor.fixtures import (
    settled_unitizer as _settled_unitizer,
)
from tests.stage_a_replay_executor.fixtures import write_spec as _write_spec
from tests.stage_a_replay_executor.fixtures import (
    write_spec_record as _write_spec_record,
)


def _accept_authorization_signature(
    _artifact_payload: bytes,
    *,
    signature_path: Path,
    signer_principal: str,
    namespace: str,
) -> None:
    del signature_path, signer_principal, namespace


def test_fake_provider_full_path_halts_at_ceiling_and_routes_exhaustion(
    tmp_path: Path,
) -> None:
    spec_path = _write_spec(tmp_path, aggregate_ceiling="0.50")
    calls: list[tuple[str, str]] = []

    def unitizer(request: CandidateScopedStageARerunRequest) -> StageAStageOutcome:
        calls.append(("unitizer", request.candidate_id))
        if request.candidate_id == "cand-b":
            return StageAStageOutcome(
                candidate_id=request.candidate_id,
                records=(
                    {
                        "candidate_id": request.candidate_id,
                        "case_id": request.packet.case_id,
                        "prediction_units": [],
                    },
                ),
                audit={
                    "candidate_id": request.candidate_id,
                    "case_id": request.packet.case_id,
                    "status": "terminal_escalation",
                    "attempt_count": 3,
                    "actual_cost_usd": "0.10",
                },
                status="terminal_escalation",
                request_sha256=request.request_sha256,
            )
        return _settled_unitizer(request)

    def reviewer(
        request: CandidateScopedStageARerunRequest,
        _unitize: StageAStageOutcome,
    ) -> StageAStageOutcome:
        calls.append(("reviewer", request.candidate_id))
        return _settled_reviewer(request, _unitize)

    result = execute_stage_a_replay(
        spec_path,
        unitizer=unitizer,
        reviewer=reviewer,
        spend_meter=_FakeSpendMeter(
            attempts_by_call={("cand-b", "unitizer"): 3},
            maximum_new_attempts_by_call={
                ("cand-b", "unitizer"): 3,
                ("cand-c", "reviewer"): 2,
            },
        ),
        code_commit="0" * 40,
    )

    assert result.halted is True
    assert calls == [
        ("unitizer", "cand-a"),
        ("reviewer", "cand-a"),
        ("unitizer", "cand-b"),
        ("unitizer", "cand-c"),
    ]
    receipt = result.to_record()
    assert receipt["stage_a_receipt_sha256"] is None
    assert receipt["halt_evidence"] == {
        "status": "halted_at_ceiling",
        "reason": (
            "reviewer invocation for candidate cand-c would exceed the signed "
            "aggregate replay ceiling"
        ),
        "candidate_id": "cand-c",
        "stage": "reviewer",
        "provider_accessed": True,
    }
    journal_value: object = json.loads((tmp_path / "invocations.json").read_text())
    assert isinstance(journal_value, dict)
    journal = cast(dict[str, object], journal_value)
    invocations = journal["invocations"]
    assert isinstance(invocations, list)
    typed_invocations = cast(list[dict[str, object]], invocations)
    exhausted = next(
        row for row in typed_invocations if row["candidate_id"] == "cand-b"
    )
    assert exhausted["attempt_count"] == 3
    assert exhausted["terminal_route"] == "qsp.attorney_adjudication"
    assert ("reviewer", "cand-b") not in calls
    assert len([row for row in calls if row[1] == "cand-b"]) == 1
    receipt_value: object = json.loads((tmp_path / "receipt.json").read_text())
    assert isinstance(receipt_value, dict)
    assert receipt_value["halted"] is True


def test_success_persists_and_replays_every_bound_artifact(tmp_path: Path) -> None:
    parsed = load_replay_spec(
        _write_spec(
            tmp_path,
            aggregate_ceiling="0.30",
            per_candidate_ceiling="0.30",
            candidate_ids=("cand-a",),
        )
    )

    result = execute_stage_a_replay(
        parsed,
        unitizer=_settled_unitizer,
        reviewer=_settled_reviewer,
        spend_meter=_FakeSpendMeter(),
        code_commit="0" * 40,
    )

    assert result.halted is False
    assert result.plan is not None
    assert result.execution is not None
    assert result.stage_a_receipt is not None
    receipt = result.to_record()
    assert receipt["plan_sha256"] == result.plan.plan_sha256
    assert receipt["execution_sha256"] == result.execution.execution_sha256
    assert receipt["stage_a_receipt_sha256"] == result.stage_a_receipt.receipt_sha256
    assert receipt["configuration_hashes"] == dict(parsed.config_hashes)
    assert receipt["model_ids"] == dict(parsed.model_ids)
    assert receipt["halt_evidence"] is None
    artifacts = cast(dict[str, object], receipt["artifacts"])
    assert all(value is not None for value in artifacts.values())
    journal_value = json.loads(
        parsed.output_paths["invocation_journal_path"].read_text()
    )
    assert isinstance(journal_value, dict)
    journal = cast(dict[str, object], journal_value)
    spend_summary = cast(dict[str, object], journal["spend_summary"])
    rows = cast(list[dict[str, object]], journal["invocations"])
    assert spend_summary["aggregate_actual_cost_usd"] == "0.20"
    assert [row["stage"] for row in rows] == [
        "unitizer",
        "reviewer",
    ]
    assert all(row["code_commit"] == "0" * 40 for row in rows)
    assert all(row["config_sha256"] for row in rows)
    assert all(cast(str, row["model_id"]).startswith("fixture:") for row in rows)
    assert all(
        cast(str, row["logical_call_key"]).startswith("fixture:cand-a:") for row in rows
    )


def test_raising_spec_ceiling_moves_the_deterministic_halt_point(
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, str]] = []

    def unitizer(request: CandidateScopedStageARerunRequest) -> StageAStageOutcome:
        calls.append(("unitizer", request.candidate_id))
        if request.candidate_id == "cand-b":
            outcome = _settled_unitizer(request)
            return StageAStageOutcome(
                candidate_id=outcome.candidate_id,
                records=outcome.records,
                audit={
                    **outcome.audit,
                    "status": "terminal_escalation",
                    "attempt_count": 3,
                },
                status="terminal_escalation",
                request_sha256=outcome.request_sha256,
            )
        return _settled_unitizer(request)

    def reviewer(
        request: CandidateScopedStageARerunRequest,
        _unitize: StageAStageOutcome,
    ) -> StageAStageOutcome:
        calls.append(("reviewer", request.candidate_id))
        return _settled_reviewer(request, _unitize)

    result = execute_stage_a_replay(
        _write_spec(tmp_path, aggregate_ceiling="0.60"),
        unitizer=unitizer,
        reviewer=reviewer,
        spend_meter=_FakeSpendMeter(
            attempts_by_call={("cand-b", "unitizer"): 3},
            maximum_new_attempts_by_call={
                ("cand-b", "unitizer"): 3,
                ("cand-c", "reviewer"): 2,
            },
        ),
        code_commit="0" * 40,
    )
    assert result.halted is False
    assert calls[-1] == ("reviewer", "cand-c")


def test_corrupt_replay_spec_hash_refuses_before_journal_or_provider_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _write_spec(tmp_path, aggregate_ceiling="0.30")
    record = json.loads(path.read_text())
    record["spend"]["aggregate_ceiling_usd"] = "9.99"
    path.write_bytes(ARTIFACT_CANONICAL_JSON_V1.encode(record))
    touched = False

    def forbidden(*_args: object, **_kwargs: object) -> object:
        nonlocal touched
        touched = True
        raise AssertionError("journal or provider accessed before replay-spec hash")

    del monkeypatch
    with pytest.raises(StageAReplayExecutorError, match="replay-spec hash mismatch"):
        execute_stage_a_replay(
            path,
            unitizer=forbidden,  # type: ignore[arg-type]
            reviewer=forbidden,  # type: ignore[arg-type]
            spend_meter=forbidden,  # type: ignore[arg-type]
        )
    assert touched is False


def test_cli_surface_accepts_only_the_hashed_replay_spec() -> None:
    parser = argparse.ArgumentParser()
    register_cli(parser.add_subparsers(dest="command"))
    parsed = parser.parse_args(["replay-stage-a", "--replay-spec", "spec.json"])
    assert parsed.replay_spec == Path("spec.json")
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "replay-stage-a",
                "--replay-spec",
                "spec.json",
                "--candidate-id",
                "cand-a",
            ]
        )


def test_public_name_string_cannot_promote_inline_packets_to_owner_authority(
    tmp_path: Path,
) -> None:
    path = _write_spec(tmp_path, candidate_ids=("cand-a",))
    record = _read_spec(path)
    authorization = cast(dict[str, object], record["authorization"])
    authorization.update(
        {
            "signature": "John Hughes",
        }
    )
    _write_spec_record(path, record, validate=False)

    with pytest.raises(
        StageAReplayExecutorError,
        match="authorization descriptor fields differ",
    ):
        load_replay_spec(path)


def test_production_execution_forbids_injected_provider_seams(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture_root = tmp_path / "fixture"
    fixture_root.mkdir()
    fixture_spec = load_replay_spec(
        _write_spec(fixture_root, candidate_ids=("cand-a",))
    )
    fixture_lineage = lineage_module.verify_replay_lineage(fixture_spec)
    production_root = tmp_path / "production"
    production_root.mkdir()
    monkeypatch.setattr(
        contract_module,
        "verify_authorization_signature",
        _accept_authorization_signature,
    )
    production_spec = load_replay_spec(
        _write_spec(production_root, candidate_ids=("cand-a",), production=True)
    )

    def fixture_verifier(_spec: object) -> object:
        return fixture_lineage

    monkeypatch.setattr(executor_module, "verify_replay_lineage", fixture_verifier)
    monkeypatch.setattr(executor_module, "current_code_commit", lambda: "0" * 40)

    result = execute_stage_a_replay(
        production_spec,
        unitizer=_settled_unitizer,
        reviewer=_settled_reviewer,
        spend_meter=_FakeSpendMeter(),
    )

    assert result.halted is True
    halt = cast(dict[str, object], result.to_record()["halt_evidence"])
    assert halt["reason"] == "production execution forbids injected provider seams"
    assert halt["provider_accessed"] is False
