# pyright: reportPrivateUsage=false, reportUnknownLambdaType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false

from __future__ import annotations

import base64
import hashlib
import inspect
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from legalforecast.evals.corpus_manifest import beads_observation as evidence
from legalforecast.evals.corpus_manifest import execution_decisions as module
from legalforecast.evals.model_registry import OpenAIReasoningEffort
from legalforecast.labeling.provider_journal import (
    PROVIDER_JOURNAL_SCHEMA_VERSION,
    ProviderAttemptJournal,
    ProviderCallIdentity,
)

# Derived, not spelled out: every other fixture here builds from
# SUCCESSOR_REGISTRY_KEYS, so an official-model swap lands atomically. A
# hard-coded key would survive the swap and silently stop perturbing any entry,
# which turns this negative test into a vacuous pass.
_ANTHROPIC_SUCCESSOR_KEY = next(
    key
    for key in sorted(evidence.SUCCESSOR_REGISTRY_KEYS)
    if key.startswith("anthropic:")
)


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write(path: Path, value: object) -> bytes:
    payload = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return payload


@pytest.fixture
def fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    cycle_id = "cycle-1"
    manifest_digest = "a" * 64
    cases = tuple(SimpleNamespace(candidate_id=f"case-{i}") for i in range(100))
    prediction_units_source = {
        "path": str(tmp_path / "finalized-units.jsonl"),
        "sha256": "d" * 64,
    }
    entries = tuple(
        SimpleNamespace(
            provider=key.split(":", 1)[0],
            model_id=key.split(":", 1)[1],
            registry_key=key,
            network_disabled=True,
            search_disabled=True,
            temperature=0.0,
            top_p=1.0,
            reasoning_effort=(
                OpenAIReasoningEffort.HIGH if key.startswith("openai:") else None
            ),
            tool_policy=SimpleNamespace(value="controlled_docket_tool_only"),
        )
        for key in sorted(evidence.SUCCESSOR_REGISTRY_KEYS)
    )
    monkeypatch.setattr(
        module,
        "load_signed_manifest_bytes",
        lambda _payload, expected_digest: SimpleNamespace(
            cycle_id=cycle_id,
            cases=cases,
            prediction_units_source=SimpleNamespace(
                to_record=lambda: prediction_units_source
            ),
        ),
    )
    monkeypatch.setattr(
        module,
        "load_model_registry_bytes",
        lambda _payload: SimpleNamespace(entries=entries),
    )
    monkeypatch.setattr(
        evidence,
        "load_model_registry_bytes",
        lambda _payload: SimpleNamespace(entries=entries),
    )
    monkeypatch.setattr(
        module, "require_official_registry_entries", lambda value: value
    )
    monkeypatch.setattr(
        evidence, "require_official_registry_entries", lambda value: value
    )
    monkeypatch.setattr(
        module,
        "registry_record",
        lambda value: [
            {"provider": entry.provider, "model_id": entry.model_id} for entry in value
        ],
    )
    monkeypatch.setattr(module, "verify_labeling_policy", lambda *args, **kwargs: "ok")
    monkeypatch.setattr(
        module,
        "verify_cohort_policy",
        lambda *args, **kwargs: module._CURRENT_COHORT_POLICY_SHA256,
    )
    monkeypatch.setattr(
        module, "verify_observation_manifest", lambda *args, **kwargs: "last"
    )
    monkeypatch.setattr(
        module,
        "load_provider_cycle_caps_bytes",
        lambda *_args, **_kwargs: SimpleNamespace(
            cycle_id=cycle_id,
            execution_attempt_policy=lambda ledger: {
                "authority_backend": "dynamodb",
                "authority_resource_identity_sha256": "b" * 64,
                "ledger_scope_fields": ["cycle_id", "provider", "account"],
                "provider_account_caps": [
                    {
                        "provider": "openai",
                        "account": "openai-primary",
                        "cap_microusd": 4_000_000,
                    },
                    {
                        "provider": "anthropic",
                        "account": "anthropic-primary",
                        "cap_microusd": 4_000_000,
                    },
                ],
                "reservation_ledger_sha256": ledger,
                "max_billable_attempts": 1,
                "failure_threshold": 1,
                "failure_window_seconds": 1,
            },
        ),
    )

    owner = tmp_path / "owner-manifest.json"
    _write(owner, {"cycle_id": cycle_id, "manifest_sha256": manifest_digest})
    registry = tmp_path / evidence.SUCCESSOR_REGISTRY_PATH
    _write(registry, [])
    caps = tmp_path / "provider-caps.json"
    _write(caps, {})
    labeling_caps = tmp_path / "labeling-provider-caps.json"
    _write(labeling_caps, {})
    provider_journal = tmp_path / "provider-attempts.sqlite3"
    labeling = tmp_path / "labeling-policy.json"
    _write(labeling, {"policy": {"published_at": "2026-01-01T00:00:00Z"}})
    cohort = tmp_path / "cohort-policy.json"
    _write(cohort, {"policy": {"cycle_id": cycle_id}})
    observation = tmp_path / "cohort-observation.jsonl"
    observation.write_bytes(b"{}\n")
    monkeypatch.setattr(
        module, "_CURRENT_COHORT_OBSERVATION_SHA256", _sha(observation.read_bytes())
    )
    monkeypatch.setattr(
        module,
        "_authenticate_provider_journal",
        lambda *_args, **_kwargs: {
            "earliest_reserved_at": "2026-01-02T00:00:00Z",
            "attempt_count": 1,
        },
    )

    forecast = tmp_path / "forecast"
    packets: list[dict[str, Any]] = []
    prompt_commitments: dict[str, str] = {}
    for case in cases:
        for ablation in module._ABLATIONS:
            packet = forecast / "model-packets" / f"{case.candidate_id}-{ablation}.json"
            packet_bytes = _write(packet, {"candidate_id": case.candidate_id})
            prompt_sha = "c" * 64
            packets.append(
                {
                    "candidate_id": case.candidate_id,
                    "case_id": case.candidate_id,
                    "ablation": ablation,
                    "packet_object_key": str(packet.relative_to(forecast)),
                    "packet_sha256": _sha(packet_bytes),
                    "prompt_sha256": prompt_sha,
                }
            )
            prompt_commitments[f"{case.candidate_id}:{ablation}"] = prompt_sha
    run_record = {
        "schema_version": "legalforecast.manifest_mode_forecast_run_record.v1",
        "generated_at": "2026-01-03T00:00:00Z",
        "manifest_sha256": manifest_digest,
        "cycle_id": cycle_id,
        "entry_mode": "owner_signed_manifest",
        "case_count": len(cases),
        "packet_count": len(packets),
        "packet_ablations": list(module._ABLATIONS),
        "provider_calls_made": 0,
        "docket_tool_enabled": False,
        "required_eval_run_case_flags": ["--no-docket-tool"],
        "evaluation_models": [
            {"provider": entry.provider, "model_id": entry.model_id}
            for entry in entries
        ],
        "prompt_commitments": prompt_commitments,
        "owner_signature_reference": {
            "bead_id": "legalforecastbench-test",
            "approval_line": (
                "I approve corpus manifest "
                + manifest_digest
                + " as the frozen Cycle 1 forecast corpus."
            ),
        },
        "prediction_units_source": prediction_units_source,
    }
    _write(forecast / "manifest-mode-run-record.json", run_record)
    _write(
        forecast / "run-inputs.json",
        {
            "cycle_id": cycle_id,
            "generated_at": "2026-01-03T00:00:00Z",
            "model_packets": packets,
        },
    )

    raw_beads = tmp_path / "bd-comments.json"
    comments = [
        {
            "id": f"comment-{index}",
            "issue_id": evidence.COORDINATION_BEAD_ID,
            "author": evidence.OWNER_AUTHOR,
            "text": text,
            "created_at": f"2026-01-0{index}T00:00:00Z",
        }
        for index, text in enumerate(
            (
                (
                    f"I approve corpus manifest {manifest_digest} as the frozen "
                    "Cycle 1 "
                    "forecast corpus."
                ),
                evidence.CONTAMINATION_LINE,
                (
                    "I approve up to USD 10.00 of provider spend for the Cycle 1 "
                    "forecast run, estimated USD 1.00, across the four models in `"
                    + evidence.SUCCESSOR_REGISTRY_PATH
                    + "`."
                ),
            ),
            start=1,
        )
    ]
    _write(raw_beads, comments)
    monkeypatch.setattr(module, "_capture_beads_comments", raw_beads.read_bytes)
    beads = tmp_path / "beads-observation.json"
    module.issue_beads_observation(
        model_registry=registry,
        output=beads,
    )
    freeze = tmp_path / "freeze-inputs"
    freeze_payloads: dict[str, bytes] = {}
    for name, value in (
        ("prompt-contract.json", {"role": "prompt"}),
        ("scorer-contract.json", {"role": "scorer"}),
        ("harness-contract.json", {"role": "harness"}),
        (
            "no-baselines.json",
            {
                "schema_version": "legalforecast.no_baselines.v1",
                "cycle_id": cycle_id,
                "status": "unavailable",
            },
        ),
        ("complete-exclusion-ledger.jsonl", {"candidate_id": "excluded"}),
    ):
        freeze_payloads[name] = _write(freeze / name, value)
    card = {
        "status": "completed",
        "cycle_id": cycle_id,
        "provider_calls_made": 0,
        "output_commitments": {
            name: _sha(payload) for name, payload in freeze_payloads.items()
        },
    }
    freeze_payloads["run-cards/issue-manifest-freeze-inputs.json"] = _write(
        freeze / "run-cards/issue-manifest-freeze-inputs.json", card
    )
    prompt_replay = {
        "owner_manifest_bytes_sha256": _sha(owner.read_bytes()),
        "model_registry_sha256": _sha(registry.read_bytes()),
        "run_inputs_sha256": _sha((forecast / "run-inputs.json").read_bytes()),
        "run_record_sha256": _sha(
            (forecast / "manifest-mode-run-record.json").read_bytes()
        ),
        "packet_count": len(packets),
        "candidate_count": len(cases),
        "prompt_commitments": prompt_commitments,
    }
    freeze_payloads["prompt-contract.json"] = _write(
        freeze / "prompt-contract.json", {"prompt_replay": prompt_replay}
    )
    card["input_paths"] = {
        "owner_manifest": str(owner),
        "model_registry": str(registry),
        "forecast_output_dir": str(forecast),
    }
    card["output_commitments"]["prompt-contract.json"] = _sha(
        freeze_payloads["prompt-contract.json"]
    )
    freeze_payloads["run-cards/issue-manifest-freeze-inputs.json"] = _write(
        freeze / "run-cards/issue-manifest-freeze-inputs.json", card
    )

    def freeze_verifier(_root: Path) -> SimpleNamespace:
        return SimpleNamespace(payloads=freeze_payloads, run_card=card)

    return {
        "owner": owner,
        "forecast": forecast,
        "registry": registry,
        "caps": caps,
        "labeling_caps": labeling_caps,
        "provider_journal": provider_journal,
        "labeling": labeling,
        "cohort": cohort,
        "observation": observation,
        "beads": beads,
        "freeze": freeze,
        "freeze_verifier": freeze_verifier,
        "output": tmp_path / "execution-decisions",
    }


def test_successor_registry_safety_ignores_legacy_sampling_fields() -> None:
    entries = tuple(
        SimpleNamespace(
            provider=key.split(":", 1)[0],
            model_id=key.split(":", 1)[1],
            registry_key=key,
            network_disabled=True,
            search_disabled=True,
            temperature=0.7,
            top_p=0.2,
            reasoning_effort=(
                OpenAIReasoningEffort.HIGH if key.startswith("openai:") else None
            ),
            tool_policy=SimpleNamespace(value="controlled_docket_tool_only"),
        )
        for key in sorted(evidence.SUCCESSOR_REGISTRY_KEYS)
    )

    module._require_successor_registry_safety(entries)


@pytest.mark.parametrize(
    ("registry_key", "reasoning_effort"),
    (
        ("openai:gpt-5.6-sol", None),
        ("openai:gpt-5.6-terra", OpenAIReasoningEffort.MEDIUM),
        (_ANTHROPIC_SUCCESSOR_KEY, OpenAIReasoningEffort.HIGH),
    ),
)
def test_successor_registry_safety_requires_exact_reasoning_settings(
    registry_key: str,
    reasoning_effort: OpenAIReasoningEffort | None,
) -> None:
    entries = tuple(
        SimpleNamespace(
            provider=key.split(":", 1)[0],
            model_id=key.split(":", 1)[1],
            registry_key=key,
            network_disabled=True,
            search_disabled=True,
            reasoning_effort=(
                reasoning_effort
                if key == registry_key
                else (OpenAIReasoningEffort.HIGH if key.startswith("openai:") else None)
            ),
            tool_policy=SimpleNamespace(value="controlled_docket_tool_only"),
        )
        for key in sorted(evidence.SUCCESSOR_REGISTRY_KEYS)
    )

    with pytest.raises(module.ExecutionDecisionsError, match="reasoning settings"):
        module._require_successor_registry_safety(entries)


def _issue(fixture: dict[str, Any]) -> module.ExecutionDecisionsBuild:
    return module.issue_execution_decisions(
        owner_manifest=fixture["owner"],
        forecast_output_dir=fixture["forecast"],
        model_registry=fixture["registry"],
        provider_cycle_caps=fixture["caps"],
        labeling_provider_cycle_caps=fixture["labeling_caps"],
        provider_journal=fixture["provider_journal"],
        labeling_policy=fixture["labeling"],
        cohort_policy=fixture["cohort"],
        cohort_observation_manifest=fixture["observation"],
        freeze_inputs_root=fixture["freeze"],
        output_root=fixture["output"],
        verify_freeze_inputs=fixture["freeze_verifier"],
    )


def test_issue_and_verify_derives_four_by_two_policy(fixture: dict[str, Any]) -> None:
    build = _issue(fixture)
    assert (fixture["output"] / "beads-observation-v2.json").is_file()
    assert "beads_observation" not in build.run_card["input_paths"]
    assert build.decisions["allow_no_baselines"] is True
    policy = build.execution_policy["policy"]
    assert policy["labeling_policy_sha256"] == _sha(fixture["labeling"].read_bytes())
    assert len(policy["shard_schedule"]["shards"]) == 8
    assert policy["repeat_policy"] == {"case_ids": [], "count": 1}
    verified = module.verify_execution_decisions(
        fixture["output"], verify_freeze_inputs=fixture["freeze_verifier"]
    )
    assert verified.decisions == build.decisions


def test_issue_is_create_only(fixture: dict[str, Any]) -> None:
    _issue(fixture)
    with pytest.raises(module.ExecutionDecisionsError, match="already exists"):
        _issue(fixture)


def test_packet_drift_is_rejected(fixture: dict[str, Any]) -> None:
    _issue(fixture)
    packet = next(fixture["forecast"].glob("model-packets/*.json"))
    packet.write_bytes(b"changed\n")
    with pytest.raises(module.ExecutionDecisionsError, match="packet changed"):
        module.verify_execution_decisions(
            fixture["output"], verify_freeze_inputs=fixture["freeze_verifier"]
        )


@pytest.mark.parametrize("verify_existing", [False, True])
def test_execution_decisions_reject_symlink_packet_for_issue_and_verification(
    fixture: dict[str, Any], verify_existing: bool
) -> None:
    if verify_existing:
        _issue(fixture)
    packet = next(fixture["forecast"].glob("model-packets/*.json"))
    target = packet.with_name("packet-target.json")
    packet.rename(target)
    packet.symlink_to(target.name)

    with pytest.raises(
        module.ExecutionDecisionsError, match="cannot read forecast packet"
    ):
        if verify_existing:
            module.verify_execution_decisions(
                fixture["output"], verify_freeze_inputs=fixture["freeze_verifier"]
            )
        else:
            _issue(fixture)


def test_observation_extra_line_is_rejected(fixture: dict[str, Any]) -> None:
    _issue(fixture)
    published = fixture["output"] / "beads-observation-v2.json"
    value = json.loads(published.read_text())
    value["extra"] = {"text": "x", "sha256": _sha(b"x")}
    _write(published, value)
    with pytest.raises(module.ExecutionDecisionsError, match="fields are not exact"):
        module.verify_execution_decisions(
            fixture["output"], verify_freeze_inputs=fixture["freeze_verifier"]
        )


def test_live_beads_observation_issuer_binds_exact_lines(
    fixture: dict[str, Any], tmp_path: Path
) -> None:
    raw = tmp_path / "bd-show.json"
    wrapper_record = json.loads(fixture["beads"].read_bytes())
    raw.write_bytes(base64.b64decode(wrapper_record["raw_observation_base64"]))
    output = tmp_path / "beads-wrapper.json"
    wrapper = module.issue_beads_observation(
        model_registry=fixture["registry"],
        output=output,
    )
    assert wrapper["raw_observation_sha256"] == _sha(raw.read_bytes())
    assert output.exists()


def _raw_comments(fixture: dict[str, Any]) -> list[dict[str, str]]:
    wrapper = json.loads(fixture["beads"].read_bytes())
    return json.loads(base64.b64decode(wrapper["raw_observation_base64"]))


def test_live_beads_capture_failure_is_domain_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=2, stdout=b"", stderr=b"Dolt unavailable"
        ),
    )

    with pytest.raises(module.ExecutionDecisionsError, match="Dolt unavailable"):
        module._capture_beads_comments()


def test_beads_issuer_has_no_raw_observation_parameter() -> None:
    assert (
        "raw_observation"
        not in inspect.signature(module.issue_beads_observation).parameters
    )


def test_critical_issuer_has_no_beads_observation_parameter() -> None:
    assert (
        "beads_observation"
        not in inspect.signature(module.issue_execution_decisions).parameters
    )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda rows: rows[0].update(issue_id="wrong"), "issue_id differs"),
        (
            lambda rows: [row.update(author="not-owner") for row in rows],
            "no owner comments",
        ),
        (
            lambda rows: rows.pop(0),
            "lacks a digest-bound manifest approval",
        ),
        (
            lambda rows: rows.pop(1),
            "lacks exact contamination replacement ruling",
        ),
        (
            lambda rows: rows.pop(2),
            "lacks final successor-registry spend approval",
        ),
    ],
)
def test_beads_parser_rejects_wrong_or_missing_authority(
    fixture: dict[str, Any], mutation: Any, message: str
) -> None:
    comments = _raw_comments(fixture)
    mutation(comments)

    with pytest.raises(module.ExecutionDecisionsError, match=message):
        module._parse_authentic_beads_comments(
            json.dumps(comments).encode(),
            model_registry=fixture["registry"],
            model_registry_bytes=fixture["registry"].read_bytes(),
        )


def test_unrelated_lifecycle_comment_is_not_execution_evidence(
    fixture: dict[str, Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    comments = _raw_comments(fixture)
    comments.append(
        {
            "id": "comment-lifecycle",
            "issue_id": evidence.COORDINATION_BEAD_ID,
            "author": evidence.OWNER_AUTHOR,
            "text": "lifecycle: labeling began at a caller-supplied timestamp",
            "created_at": "2026-01-09T00:00:00Z",
        }
    )
    monkeypatch.setattr(
        module, "_capture_beads_comments", lambda: json.dumps(comments).encode()
    )

    wrapper = module.issue_beads_observation(
        model_registry=fixture["registry"],
        output=tmp_path / "lifecycle-irrelevant.json",
    )

    assert set(wrapper["evidence"]) == {
        "manifest",
        "contamination",
        "final_provider_spend",
    }


def test_rehashed_forged_beads_evidence_is_rejected(fixture: dict[str, Any]) -> None:
    _issue(fixture)
    published = fixture["output"] / "beads-observation-v2.json"
    wrapper = json.loads(published.read_bytes())
    forged = (
        "I approve corpus manifest "
        + "f" * 64
        + " as the frozen Cycle 1 forecast corpus."
    )
    wrapper["evidence"]["manifest"]["text"] = forged
    wrapper["evidence"]["manifest"]["text_sha256"] = _sha(forged.encode())
    _write(published, wrapper)

    with pytest.raises(module.ExecutionDecisionsError, match="does not replay"):
        module.verify_execution_decisions(
            fixture["output"], verify_freeze_inputs=fixture["freeze_verifier"]
        )


def test_execution_decisions_reject_unsafe_registry(
    fixture: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    entries = module.load_model_registry_bytes(b"").entries
    entries[0].network_disabled = False
    monkeypatch.setattr(
        module,
        "load_model_registry_bytes",
        lambda _payload: SimpleNamespace(entries=entries),
    )

    with pytest.raises(module.ExecutionDecisionsError, match="unsafe execution"):
        _issue(fixture)


def test_execution_decisions_reject_incomplete_provider_caps(
    fixture: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        module,
        "load_provider_cycle_caps_bytes",
        lambda *_args, **_kwargs: SimpleNamespace(
            cycle_id="cycle-1",
            execution_attempt_policy=lambda _digest: {
                "provider_account_caps": [
                    {
                        "provider": "openai",
                        "account": "openai-primary",
                        "cap_microusd": 1_000_000,
                    }
                ]
            },
        ),
    )

    with pytest.raises(module.ExecutionDecisionsError, match="exactly cover"):
        _issue(fixture)


def test_execution_decisions_reject_labeling_caps_for_another_cycle(
    fixture: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0

    def load_caps(*_args: Any, **_kwargs: Any) -> SimpleNamespace:
        nonlocal calls
        calls += 1
        cycle_id = "cycle-1" if calls == 1 else "cycle-2"
        return SimpleNamespace(
            cycle_id=cycle_id,
            execution_attempt_policy=lambda digest: {
                "authority_backend": "dynamodb",
                "authority_resource_identity_sha256": "b" * 64,
                "ledger_scope_fields": ["cycle_id", "provider", "account"],
                "provider_account_caps": [],
                "reservation_ledger_sha256": digest,
                "max_billable_attempts": 1,
                "failure_threshold": 1,
                "failure_window_seconds": 1,
            },
        )

    monkeypatch.setattr(module, "load_provider_cycle_caps_bytes", load_caps)

    with pytest.raises(
        module.ExecutionDecisionsError, match=r"labeling provider.*cycle"
    ):
        _issue(fixture)


def test_execution_decisions_reject_caps_above_owner_ceiling(
    fixture: dict[str, Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    comments = _raw_comments(fixture)
    comments[2]["text"] = (
        "I approve up to USD 5.00 of provider spend for the Cycle 1 forecast run, "
        "estimated USD 1.00, across the four models in `"
        + evidence.SUCCESSOR_REGISTRY_PATH
        + "`."
    )
    monkeypatch.setattr(
        module, "_capture_beads_comments", lambda: json.dumps(comments).encode()
    )
    with pytest.raises(module.ExecutionDecisionsError, match="caps exceed"):
        _issue(fixture)


@pytest.mark.parametrize(
    ("reserved_at", "message"),
    [
        ("2026-01-02T00:00:00", "timezone-aware"),
        ("2025-12-31T00:00:00Z", "not published before"),
    ],
)
def test_execution_decisions_reject_invalid_journal_lifecycle(
    fixture: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    reserved_at: str,
    message: str,
) -> None:
    monkeypatch.setattr(
        module,
        "_authenticate_provider_journal",
        lambda *_args, **_kwargs: {
            "earliest_reserved_at": reserved_at,
            "attempt_count": 1,
        },
    )

    with pytest.raises(module.ExecutionDecisionsError, match=message):
        _issue(fixture)


def test_execution_decisions_reject_noncurrent_observation(
    fixture: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(module, "_CURRENT_COHORT_OBSERVATION_SHA256", "f" * 64)

    with pytest.raises(module.ExecutionDecisionsError, match="current v3 bytes"):
        _issue(fixture)


def test_execution_decisions_reject_noncurrent_cohort_policy(
    fixture: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    accepted = module._CURRENT_COHORT_POLICY_SHA256
    monkeypatch.setattr(module, "_CURRENT_COHORT_POLICY_SHA256", "f" * 64)
    monkeypatch.setattr(module, "verify_cohort_policy", lambda *_args: accepted)

    with pytest.raises(module.ExecutionDecisionsError, match="current v3 policy"):
        _issue(fixture)


def test_execution_decisions_reject_freeze_prompt_replay_drift(
    fixture: dict[str, Any],
) -> None:
    prompt = fixture["freeze"] / "prompt-contract.json"
    value = json.loads(prompt.read_bytes())
    value["prompt_replay"]["packet_count"] = 199
    _write(prompt, value)
    payloads = {
        str(path.relative_to(fixture["freeze"])): path.read_bytes()
        for path in fixture["freeze"].rglob("*")
        if path.is_file()
    }
    card = json.loads(
        (fixture["freeze"] / "run-cards/issue-manifest-freeze-inputs.json").read_bytes()
    )
    fixture["freeze_verifier"] = lambda _root: SimpleNamespace(
        payloads=payloads, run_card=card
    )

    with pytest.raises(module.ExecutionDecisionsError, match="packet_count"):
        _issue(fixture)


def test_execution_decisions_reject_symlink_input(fixture: dict[str, Any]) -> None:
    labeling = fixture["labeling"]
    target = labeling.with_name("labeling-target.json")
    labeling.rename(target)
    labeling.symlink_to(target)

    with pytest.raises(
        module.ExecutionDecisionsError, match="cannot read labeling policy"
    ):
        _issue(fixture)


def _canonical_journal_path(tmp_path: Path) -> Path:
    return (
        tmp_path
        / "cycle-1/target-100-production-v4-ranked-reserve/paid-labeling"
        / "provider-attempts.sqlite3"
    )


def _reserve_journal_attempt(
    path: Path,
    *,
    candidate_id: str,
    caps_sha256: str,
    reserved_at: str,
) -> None:
    with ProviderAttemptJournal(
        path,
        identity=ProviderCallIdentity(
            stage="llm-unitize",
            candidate_id=candidate_id,
            model_key="openai:gpt-5.6-sol",
            prompt=f"prompt for {candidate_id}",
            model_registry_sha256="b" * 64,
        ),
        provider="openai",
        reservation_usd=0.01,
        cycle_cap_usd=1.0,
        cycle_id="cycle-1",
        provider_cycle_caps_sha256=caps_sha256,
    ) as journal:
        journal.run_attempt(1, lambda: {"candidate_id": candidate_id})
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE provider_attempts SET reserved_at = ? WHERE candidate_id = ?",
            (reserved_at, candidate_id),
        )


def test_provider_journal_authentication_selects_earliest_reservation(
    tmp_path: Path,
) -> None:
    path = _canonical_journal_path(tmp_path)
    caps_sha256 = "c" * 64
    _reserve_journal_attempt(
        path,
        candidate_id="later",
        caps_sha256=caps_sha256,
        reserved_at="2026-01-03T00:00:00Z",
    )
    _reserve_journal_attempt(
        path,
        candidate_id="earlier",
        caps_sha256=caps_sha256,
        reserved_at="2026-01-02T00:00:00Z",
    )
    snapshots: dict[Path, bytes] = {}

    authenticated = module._authenticate_provider_journal(
        path,
        cycle_id="cycle-1",
        provider_cycle_caps_sha256=caps_sha256,
        snapshots=snapshots,
    )

    assert authenticated["attempt_count"] == 2
    assert authenticated["earliest_reserved_at"] == "2026-01-02T00:00:00Z"
    assert authenticated["earliest_reservation"]["candidate_id"] == "earlier"
    assert path in snapshots


def test_provider_journal_authentication_commits_live_wal(
    tmp_path: Path,
) -> None:
    path = _canonical_journal_path(tmp_path)
    caps_sha256 = "c" * 64
    with ProviderAttemptJournal(
        path,
        identity=ProviderCallIdentity(
            stage="llm-unitize",
            candidate_id="wal-row",
            model_key="openai:gpt-5.6-sol",
            prompt="prompt",
            model_registry_sha256="b" * 64,
        ),
        provider="openai",
        reservation_usd=0.01,
        cycle_cap_usd=1.0,
        cycle_id="cycle-1",
        provider_cycle_caps_sha256=caps_sha256,
    ) as journal:
        journal.run_attempt(1, lambda: {"ok": True})
        authenticated = module._authenticate_provider_journal(
            path,
            cycle_id="cycle-1",
            provider_cycle_caps_sha256=caps_sha256,
            snapshots={},
        )

    assert authenticated["attempt_count"] == 1
    assert "provider-attempts.sqlite3-wal" in authenticated["durable_files"]


def test_provider_journal_authentication_rejects_empty_journal(
    tmp_path: Path,
) -> None:
    path = _canonical_journal_path(tmp_path)
    caps_sha256 = "c" * 64
    with ProviderAttemptJournal(
        path,
        identity=ProviderCallIdentity(
            stage="llm-unitize",
            candidate_id="empty",
            model_key="openai:gpt-5.6-sol",
            prompt="prompt",
            model_registry_sha256="b" * 64,
        ),
        provider="openai",
        reservation_usd=0.01,
        cycle_cap_usd=1.0,
        cycle_id="cycle-1",
        provider_cycle_caps_sha256=caps_sha256,
    ):
        pass

    with pytest.raises(module.ExecutionDecisionsError, match="no durable reservations"):
        module._authenticate_provider_journal(
            path,
            cycle_id="cycle-1",
            provider_cycle_caps_sha256=caps_sha256,
            snapshots={},
        )


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("schema_version", "wrong.v1", "schema identity differs"),
        ("cycle_id", "cycle-2", "cycle identity differs"),
        ("provider_cycle_caps_sha256", "d" * 64, "caps artifact identity differs"),
        (
            "canonical_path",
            "/wrong/provider-attempts.sqlite3",
            "canonical path differs",
        ),
    ],
)
def test_provider_journal_authentication_rejects_wrong_identity(
    tmp_path: Path, column: str, value: str, message: str
) -> None:
    path = _canonical_journal_path(tmp_path)
    caps_sha256 = "c" * 64
    _reserve_journal_attempt(
        path,
        candidate_id="candidate",
        caps_sha256=caps_sha256,
        reserved_at="2026-01-02T00:00:00Z",
    )
    with sqlite3.connect(path) as connection:
        connection.execute(
            f"UPDATE provider_journal_metadata SET {column} = ? WHERE singleton = 1",
            (value,),
        )

    with pytest.raises(module.ExecutionDecisionsError, match=message):
        module._authenticate_provider_journal(
            path,
            cycle_id="cycle-1",
            provider_cycle_caps_sha256=caps_sha256,
            snapshots={},
        )


def test_provider_journal_authentication_rejects_noncanonical_path(
    tmp_path: Path,
) -> None:
    with pytest.raises(module.ExecutionDecisionsError, match="not the canonical"):
        module._authenticate_provider_journal(
            tmp_path / "provider-attempts.sqlite3",
            cycle_id="cycle-1",
            provider_cycle_caps_sha256="c" * 64,
            snapshots={},
        )


def test_provider_journal_authentication_wraps_sql_errors(tmp_path: Path) -> None:
    path = _canonical_journal_path(tmp_path)
    path.parent.mkdir(parents=True)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE provider_journal_metadata ("
            "singleton INTEGER, schema_version TEXT, cycle_id TEXT, "
            "provider_cycle_caps_sha256 TEXT, canonical_path TEXT)"
        )
        connection.execute(
            "INSERT INTO provider_journal_metadata VALUES (1, ?, ?, ?, ?)",
            (
                PROVIDER_JOURNAL_SCHEMA_VERSION,
                "cycle-1",
                "c" * 64,
                str(path.resolve()),
            ),
        )

    with pytest.raises(
        module.ExecutionDecisionsError, match="provider journal authentication failed"
    ):
        module._authenticate_provider_journal(
            path,
            cycle_id="cycle-1",
            provider_cycle_caps_sha256="c" * 64,
            snapshots={},
        )


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", "sNaN"])
def test_money_rejects_nonfinite_values(value: str) -> None:
    with pytest.raises(module.ExecutionDecisionsError, match="non-negative cents"):
        module._money(value, "amount")
