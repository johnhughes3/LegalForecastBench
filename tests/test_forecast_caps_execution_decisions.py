from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from legalforecast.evals.corpus_manifest import execution_decisions
from legalforecast.labeling.provider_cycle_caps_materializer import (
    _materialize_provider_cycle_caps_successor,
    load_provider_cycle_caps_successor_policy,
)

LEGACY_CAPS = Path(
    "model_registries/cycle-1-forecast-provider-caps-base-2026-08-25.json"
)
SUCCESSOR_POLICY = Path(
    "model_registries/cycle-1-forecast-provider-caps-successor-policy-2026-08-25.json"
)


def test_checked_in_forecast_caps_pass_execution_decisions_consumer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cycle_id = "cycle-1-target-100-2026-07-25"
    source = LEGACY_CAPS.read_bytes()
    policy_bytes = SUCCESSOR_POLICY.read_bytes()
    policy = load_provider_cycle_caps_successor_policy(
        policy_bytes, expected_sha256=hashlib.sha256(policy_bytes).hexdigest()
    )
    materialized = _materialize_provider_cycle_caps_successor(
        source,
        expected_source_sha256=hashlib.sha256(source).hexdigest(),
        authority_smoke=SimpleNamespace(
            byte_count=321,
            sha256="d" * 64,
            release_sha="e" * 40,
            resource_identity_sha256="a" * 64,
        ),
        policy=policy,
    )
    owner = tmp_path / "owner.json"
    owner.write_text(json.dumps({"manifest_sha256": "a" * 64, "cycle_id": cycle_id}))
    caps = tmp_path / "caps.json"
    labeling_caps = tmp_path / "labeling-caps.json"
    for path in (caps, labeling_caps):
        path.write_bytes(materialized.caps_bytes)
    registry = tmp_path / "registry.json"
    registry.write_bytes(b"registry\n")
    labeling = tmp_path / "labeling.json"
    labeling.write_text('{"policy":{"published_at":"2026-01-01T00:00:00Z"}}')
    cohort = tmp_path / "cohort.json"
    cohort.write_text(json.dumps({"policy": {"cycle_id": cycle_id}}))
    observation = tmp_path / "observation.jsonl"
    observation.write_bytes(b"{}\n")
    monkeypatch.setattr(
        execution_decisions,
        "_CURRENT_COHORT_OBSERVATION_SHA256",
        hashlib.sha256(observation.read_bytes()).hexdigest(),
    )
    forecast = tmp_path / "forecast"
    forecast.mkdir()
    entries = tuple(
        SimpleNamespace(provider=provider, registry_key=key)
        for provider, key in (
            ("openai", "openai:gpt-5.6-sol"),
            ("openai", "openai:gpt-5.6-terra"),
            ("openai", "openai:gpt-5.6-luna"),
            ("anthropic", "anthropic:claude-fable-5"),
        )
    )
    cases = tuple(SimpleNamespace(candidate_id=f"case-{i}") for i in range(100))
    beads = {
        "raw_observation_sha256": "d" * 64,
        "bead_id": "bead",
        # The consumer refuses caps whose sum exceeds the owner ceiling, so
        # this fixture ceiling tracks the shipped caps: 1705.60 anthropic
        # (Claude Fable 5 alone, per the 2026-08-31 owner ruling) + 1740.02
        # openai, both at 130% of the r4 projection per the 2026-08-30
        # roomier-caps ruling.
        "ceiling_usd": "3445.62",
        "estimate_usd": "1.00",
        "line_sha256": dict.fromkeys(
            ("manifest", "contamination", "final_provider_spend"), "e" * 64
        ),
    }
    no_baselines = json.dumps(
        {
            "schema_version": "legalforecast.no_baselines.v1",
            "cycle_id": cycle_id,
            "status": "unavailable",
        }
    ).encode()
    patches = {
        "load_signed_manifest_bytes": lambda *_a, **_k: SimpleNamespace(
            cycle_id=cycle_id,
            cases=cases,
            prediction_units_source=SimpleNamespace(to_record=lambda: {}),
        ),
        "load_model_registry_bytes": lambda _payload: SimpleNamespace(entries=entries),
        "require_official_registry_entries": lambda value: value,
        "_require_successor_registry_safety": lambda _value: None,
        "registry_record": lambda value: [
            {"provider": entry.provider, "model_id": entry.registry_key.split(":")[1]}
            for entry in value
        ],
        "_verify_forecast": lambda *_a, **_k: {
            "run_inputs_sha256": "b" * 64,
            "run_record_sha256": "c" * 64,
            "prompt_commitments": {},
        },
        "_authenticate_provider_journal": lambda *_a, **_k: {
            "earliest_reserved_at": "2026-01-02T00:00:00Z"
        },
        "verify_labeling_policy": lambda *_a, **_k: "ok",
        "verify_cohort_policy": lambda *_a, **_k: (
            execution_decisions._CURRENT_COHORT_POLICY_SHA256
        ),
        "verify_observation_manifest": lambda *_a, **_k: "ok",
        "_observation_records": lambda _value: (),
        "_capture_beads_comments": lambda: b"raw",
        "_encode_beads_observation": lambda *_a, **_k: ({}, b"beads"),
        "_verify_beads_observation": lambda *_a, **_k: beads,
        "_verify_complete_freeze_inputs": lambda *_a, **_k: {
            "no-baselines.json": no_baselines
        },
    }
    for name, value in patches.items():
        monkeypatch.setattr(execution_decisions, name, value)

    build = execution_decisions.issue_execution_decisions(
        owner_manifest=owner,
        forecast_output_dir=forecast,
        model_registry=registry,
        provider_cycle_caps=caps,
        labeling_provider_cycle_caps=labeling_caps,
        provider_journal=tmp_path / "journal.sqlite3",
        labeling_policy=labeling,
        cohort_policy=cohort,
        cohort_observation_manifest=observation,
        freeze_inputs_root=tmp_path / "freeze",
        output_root=tmp_path / "execution-decisions",
        verify_freeze_inputs=lambda _root: None,
    )

    assert build.decisions["cycle_id"] == cycle_id
    assert {
        cap["provider"]
        for cap in build.decisions["attempt_policy"]["provider_account_caps"]
    } == {"anthropic", "openai"}
