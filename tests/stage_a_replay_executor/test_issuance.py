"""Issue -> owner signature -> record -> execute, proven offline."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from legalforecast.cli_commands.stage_a_replay import register as register_cli
from legalforecast.cli_commands.stage_a_replay import (
    register_issuance as register_issuance_cli,
)
from legalforecast.ingestion.stage_a_replay_executor import (
    contract as contract_module,
)
from legalforecast.ingestion.stage_a_replay_executor import (
    executor as executor_module,
)
from legalforecast.ingestion.stage_a_replay_executor import (
    issuance as issuance_module,
)
from legalforecast.ingestion.stage_a_replay_executor import spec as spec_module
from legalforecast.ingestion.stage_a_replay_executor.contract import (
    StageAReplayExecutorError,
)
from legalforecast.ingestion.stage_a_replay_executor.executor import (
    execute_canonical_stage_a_replay,
)
from legalforecast.ingestion.stage_a_replay_executor.issuance import (
    OUTPUT_FILENAMES,
    ReplaySpecDraft,
    issue_replay_descriptor,
    write_replay_descriptor_draft,
)
from legalforecast.ingestion.stage_a_replay_executor.issuance_request import (
    load_issuance_request,
)
from legalforecast.ingestion.stage_a_replay_executor.recording import (
    record_replay_authorization,
)
from legalforecast.ingestion.stage_a_replay_executor.spec import load_replay_spec
from tests.stage_a_replay_executor.issuance_fixtures import (
    CANDIDATE_IDS,
    CAPS_SHA256,
    REGISTRY_SHA256,
    SYNTHETIC_PRINCIPAL,
    UNITIZER_ENTRY_SHA256,
    build_issuance_inputs,
    build_signing_checkout,
    read_json,
)

FIXTURE_COMMIT = "0" * 40


def test_issuer_derives_frozen_configuration_from_predecessor_cards(
    tmp_path: Path,
) -> None:
    request = load_issuance_request(build_issuance_inputs(tmp_path))

    draft = issue_replay_descriptor(request, code_commit=FIXTURE_COMMIT)

    configuration = draft.descriptor["configuration"]
    assert isinstance(configuration, dict)
    unitizer = configuration["unitizer"]
    assert isinstance(unitizer, dict)
    # Namespace, model identity, and registry pins are read out of the
    # authenticated run card, never restated by the operator.
    assert unitizer["namespace"] == "claim-ontology-v5"
    assert unitizer["prompt_contract"] == "claim-ontology-v5"
    assert unitizer["model_id"] == "fixture:unitizer"
    assert unitizer["model_entry_sha256"] == UNITIZER_ENTRY_SHA256
    assert unitizer["model_registry_sha256"] == REGISTRY_SHA256
    assert unitizer["provider_caps_sha256"] == CAPS_SHA256
    provider = draft.descriptor["provider"]
    assert isinstance(provider, dict)
    assert provider["model_registry_sha256"] == REGISTRY_SHA256
    assert provider["provider_caps_sha256"] == CAPS_SHA256
    lineage = draft.descriptor["lineage"]
    assert isinstance(lineage, dict)
    assert lineage["mode"] == "verified_artifacts"


def test_issuer_binds_repair_evidence_to_the_bytes_present_at_issuance(
    tmp_path: Path,
) -> None:
    request = load_issuance_request(build_issuance_inputs(tmp_path))
    draft = issue_replay_descriptor(request, code_commit=FIXTURE_COMMIT)
    lineage = draft.descriptor["lineage"]
    assert isinstance(lineage, dict)
    repair = lineage["repair_receipt"]
    assert isinstance(repair, dict)
    receipt_path = Path(str(repair["receipt_path"]))
    recorded = repair["receipt_artifact_sha256"]

    receipt_path.write_bytes(b"tampered repair receipt\n")
    reissued = issue_replay_descriptor(request, code_commit=FIXTURE_COMMIT)

    relineage = reissued.descriptor["lineage"]
    assert isinstance(relineage, dict)
    rerepair = relineage["repair_receipt"]
    assert isinstance(rerepair, dict)
    assert rerepair["receipt_artifact_sha256"] != recorded
    assert reissued.descriptor_sha256 != draft.descriptor_sha256


def test_issuer_refuses_ceilings_the_reservation_guard_could_never_satisfy(
    tmp_path: Path,
) -> None:
    """A ceiling below reservation x 3 halts deterministically with no spend.

    Regression for the Leg 1 halt: ``guard.guarded_callback`` reserves the full
    three-attempt allowance before the first provider call, so issuing such a
    spec burns an owner authorization window instead of saving money.
    """

    request = load_issuance_request(
        build_issuance_inputs(
            tmp_path,
            per_candidate_ceiling="1.776",
            hard_ceiling="8.88",
            estimated_cost="4.44",
            unitizer_reservation="3.768",
            reviewer_reservation="2.064384",
        )
    )

    with pytest.raises(StageAReplayExecutorError) as error:
        issue_replay_descriptor(request, code_commit=FIXTURE_COMMIT)

    message = str(error.value)
    assert "unitizer reservation USD 3.768" in message
    assert "USD 11.304" in message
    assert "per-candidate ceiling USD 1.776" in message


def test_issuer_refuses_a_per_candidate_ceiling_above_the_aggregate(
    tmp_path: Path,
) -> None:
    request = load_issuance_request(
        build_issuance_inputs(
            tmp_path,
            per_candidate_ceiling="12.01",
            hard_ceiling="12.00",
            estimated_cost="1.00",
        )
    )

    with pytest.raises(StageAReplayExecutorError) as error:
        issue_replay_descriptor(request, code_commit=FIXTURE_COMMIT)

    assert "per-candidate ceiling exceeds the aggregate hard ceiling" in str(
        error.value
    )


def test_issuer_refuses_a_predecessor_card_outside_the_frozen_namespace(
    tmp_path: Path,
) -> None:
    request_path = build_issuance_inputs(tmp_path)
    request = load_issuance_request(request_path)
    card_path = tmp_path / "inputs" / "llm-unitize.json"
    card = read_json(card_path)
    execution = card["model_execution"]
    assert isinstance(execution, dict)
    execution["provider_attempt_namespace"] = "claim-ontology-v4"
    card_path.write_text(json.dumps(card), encoding="utf-8")

    with pytest.raises(StageAReplayExecutorError) as error:
        issue_replay_descriptor(request, code_commit=FIXTURE_COMMIT)

    assert "not frozen claim-ontology-v5" in str(error.value)


def test_recorder_refuses_approval_text_that_omits_the_descriptor_hash(
    tmp_path: Path,
) -> None:
    _checkout, key, head = build_signing_checkout(tmp_path)
    draft, _ = _issued_draft(tmp_path, head)

    with pytest.raises(StageAReplayExecutorError) as error:
        record_replay_authorization(
            draft.descriptor,
            approval_text=(
                "I approve candidates cand-a, cand-b at estimated cost USD 6.00 "
                "and hard ceiling USD 12.00."
            ),
            request_artifact_path=tmp_path / "inputs" / "request.md",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            estimated_cost_usd=Decimal("6.00"),
            hard_ceiling_usd=Decimal("12.00"),
            signer_principal=SYNTHETIC_PRINCIPAL,
            output_dir=tmp_path / "recorded",
            signing_key=key,
        )

    assert draft.descriptor_sha256 in str(error.value)


def test_recorder_refuses_to_author_owner_approval(tmp_path: Path) -> None:
    _checkout, key, head = build_signing_checkout(tmp_path)
    draft, _ = _issued_draft(tmp_path, head)

    with pytest.raises(StageAReplayExecutorError) as error:
        record_replay_authorization(
            draft.descriptor,
            approval_text="   \n",
            request_artifact_path=tmp_path / "inputs" / "request.md",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            estimated_cost_usd=Decimal("6.00"),
            hard_ceiling_usd=Decimal("12.00"),
            signer_principal=SYNTHETIC_PRINCIPAL,
            output_dir=tmp_path / "recorded",
            signing_key=key,
        )

    assert "never authors it" in str(error.value)


def test_issue_record_round_trip_is_accepted_by_the_executor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The recorded spec loads, authorizes, and reaches lineage without spend."""

    _checkout, key, head = build_signing_checkout(tmp_path)
    draft, descriptor_path = _issued_draft(tmp_path, head)
    _patch_repository_root(monkeypatch, _checkout)

    recorded = record_replay_authorization(
        draft.descriptor,
        approval_text=draft.approval_text,
        request_artifact_path=tmp_path / "inputs" / "request.md",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        estimated_cost_usd=draft.estimated_cost_usd,
        hard_ceiling_usd=draft.hard_ceiling_usd,
        signer_principal=SYNTHETIC_PRINCIPAL,
        output_dir=tmp_path / "recorded",
        signing_key=key,
    )

    assert descriptor_path.is_file()
    assert recorded.descriptor_sha256 == draft.descriptor_sha256
    # The executor's own loader accepts the artifact: canonical hash, detached
    # SSH signature against the allowed-signers file, expiry, ceilings, and
    # output isolation all verify.
    reloaded = load_replay_spec(recorded.spec_path)
    assert reloaded.spec_sha256 == recorded.spec_sha256
    assert reloaded.candidate_ids == CANDIDATE_IDS
    assert reloaded.synthetic_fixture is False
    assert set(reloaded.output_paths) == set(OUTPUT_FILENAMES)

    result = execute_canonical_stage_a_replay(recorded.spec_path)

    # Authorization is accepted; the run halts on the deliberately absent
    # fixture lineage, never on authority, and never opens a provider.
    assert result.halted is True
    assert result.spec_sha256 == recorded.spec_sha256
    record = result.to_record()
    halt = record["halt_evidence"]
    assert isinstance(halt, dict)
    assert halt["provider_accessed"] is False
    assert "lineage" in str(halt["reason"]).lower()
    assert record["authorized_candidate_ids"] == list(CANDIDATE_IDS)
    assert record["plan_sha256"] is None


def test_one_tampered_byte_makes_the_executor_refuse_naming_the_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _checkout, key, head = build_signing_checkout(tmp_path)
    draft, _ = _issued_draft(tmp_path, head)
    _patch_repository_root(monkeypatch, _checkout)
    recorded = record_replay_authorization(
        draft.descriptor,
        approval_text=draft.approval_text,
        request_artifact_path=tmp_path / "inputs" / "request.md",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        estimated_cost_usd=draft.estimated_cost_usd,
        hard_ceiling_usd=draft.hard_ceiling_usd,
        signer_principal=SYNTHETIC_PRINCIPAL,
        output_dir=tmp_path / "recorded",
        signing_key=key,
    )
    payload = recorded.spec_path.read_bytes()
    marker = b'"cand-a"'
    assert marker in payload
    recorded.spec_path.write_bytes(payload.replace(marker, b'"cand-b"', 1))

    with pytest.raises(StageAReplayExecutorError) as error:
        execute_canonical_stage_a_replay(recorded.spec_path)

    message = str(error.value)
    assert "replay-spec hash mismatch" in message
    assert recorded.spec_sha256 in message
    assert "(replay-spec hash)" in message


def test_a_resigned_tamper_still_fails_the_owner_descriptor_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rehashing a mutated spec does not restore authority.

    The signed authorization commits to the descriptor hash, so an attacker who
    can rewrite ``replay_spec_sha256`` still cannot move the operative fields.
    """

    _checkout, key, head = build_signing_checkout(tmp_path)
    draft, _ = _issued_draft(tmp_path, head)
    _patch_repository_root(monkeypatch, _checkout)
    recorded = record_replay_authorization(
        draft.descriptor,
        approval_text=draft.approval_text,
        request_artifact_path=tmp_path / "inputs" / "request.md",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        estimated_cost_usd=draft.estimated_cost_usd,
        hard_ceiling_usd=draft.hard_ceiling_usd,
        signer_principal=SYNTHETIC_PRINCIPAL,
        output_dir=tmp_path / "recorded",
        signing_key=key,
    )
    record = read_json(recorded.spec_path)
    spend = record["spend"]
    assert isinstance(spend, dict)
    spend["aggregate_ceiling_usd"] = "99.00"
    del record["replay_spec_sha256"]
    record["replay_spec_sha256"] = contract_module.sha256_bytes(
        contract_module.canonical(record)
    )
    recorded.spec_path.write_bytes(contract_module.canonical(record))

    with pytest.raises(StageAReplayExecutorError) as error:
        execute_canonical_stage_a_replay(recorded.spec_path)

    assert "replay descriptor differs from replay-spec" in str(error.value)


def test_cli_issue_then_record_produces_an_executor_loadable_spec(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The two supported commands compose into the documented operator flow."""

    checkout, key, head = build_signing_checkout(tmp_path)
    _patch_repository_root(monkeypatch, checkout)
    monkeypatch.setattr(issuance_module, "current_code_commit", lambda **_kwargs: head)
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    register_cli(subparsers)
    register_issuance_cli(subparsers)

    issued = parser.parse_args(
        [
            "issue-replay-spec",
            "--issuance-request",
            str(build_issuance_inputs(tmp_path)),
            "--output-dir",
            str(tmp_path / "issued"),
            "--skip-preflight",
        ]
    )
    assert issued.handler(issued) == 0
    issue_record = json.loads(capsys.readouterr().out)
    assert issue_record["preflight"] == {"status": "skipped"}
    approval_path = tmp_path / "owner-approval.txt"
    approval_path.write_text(issue_record["approval_text"], encoding="utf-8")

    recorded = parser.parse_args(
        [
            "record-replay-authorization",
            "--replay-descriptor",
            str(tmp_path / "issued" / "replay-descriptor.json"),
            "--approval-text-file",
            str(approval_path),
            "--request-artifact",
            str(tmp_path / "inputs" / "request.md"),
            "--expires-at",
            (datetime.now(UTC) + timedelta(hours=2)).isoformat(),
            "--estimated-cost-usd",
            issue_record["estimated_cost_usd"],
            "--signer-principal",
            SYNTHETIC_PRINCIPAL,
            "--output-dir",
            str(tmp_path / "recorded"),
            "--signing-key",
            str(key),
        ]
    )
    assert recorded.handler(recorded) == 0

    record_output = json.loads(capsys.readouterr().out)
    assert (
        record_output["replay_descriptor_sha256"]
        == issue_record["replay_descriptor_sha256"]
    )
    spec = load_replay_spec(Path(record_output["replay_spec_path"]))
    assert spec.spec_sha256 == record_output["replay_spec_sha256"]
    assert spec.code_commit == head


def test_cli_issue_reports_a_refused_preflight_without_writing_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        issuance_module, "current_code_commit", lambda **_kwargs: FIXTURE_COMMIT
    )
    parser = argparse.ArgumentParser()
    register_issuance_cli(parser.add_subparsers(dest="command"))
    issued = parser.parse_args(
        [
            "issue-replay-spec",
            "--issuance-request",
            str(build_issuance_inputs(tmp_path)),
            "--output-dir",
            str(tmp_path / "issued"),
        ]
    )

    assert issued.handler(issued) == 2

    record = json.loads(capsys.readouterr().out)
    preflight = record["preflight"]
    assert preflight["status"] == "refused"
    assert preflight["stage"] == "lineage"
    assert "lineage" in str(preflight["reason"]).lower()
    assert not (tmp_path / "recorded").exists()


def _issued_draft(tmp_path: Path, code_commit: str) -> tuple[ReplaySpecDraft, Path]:
    request = load_issuance_request(build_issuance_inputs(tmp_path))
    draft = issue_replay_descriptor(request, code_commit=code_commit)
    descriptor_path = write_replay_descriptor_draft(draft, tmp_path / "issued")
    return draft, descriptor_path


def _patch_repository_root(monkeypatch: pytest.MonkeyPatch, checkout: Path) -> None:
    """Point signature verification and checkout isolation at the fixture repo."""

    monkeypatch.setattr(contract_module, "repository_root", lambda: checkout)
    monkeypatch.setattr(spec_module, "repository_root", lambda: checkout)
    monkeypatch.setattr(executor_module, "repository_root", lambda: checkout)
