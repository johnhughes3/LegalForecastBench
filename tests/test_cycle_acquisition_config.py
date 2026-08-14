from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from legalforecast.config import (
    CYCLE_1_ID,
    CYCLE_2_ID,
    CYCLE_CONFIGS,
    CycleConfigError,
    CycleConfigNotActivatedError,
    DocumentNeedBucket,
    EvaluationRegistryPin,
    EvaluationRegistryPinError,
    SelectorModel,
    SelectorModelPolicy,
    SelectorRegistryCollisionError,
    StratificationPolicy,
    UnknownCycleConfigError,
    load_activated_cycle,
    load_cycle,
    preflight_selector_models,
    repository_root,
    require_activated,
    usd,
)
from legalforecast.evals.model_registry import load_model_registry

ROOT = Path(__file__).resolve().parents[1]
CYCLE_1_REGISTRY = ROOT / "model_registries" / "cycle-1-2026-06-30.json"


def test_registered_cycles_are_inert_and_import_validates() -> None:
    assert set(CYCLE_CONFIGS) == {CYCLE_1_ID, CYCLE_2_ID}
    cycle_1 = load_cycle(CYCLE_1_ID)
    cycle_2 = load_cycle(CYCLE_2_ID)

    assert cycle_1.legacy_pinned is True
    assert cycle_1.activated is False
    assert cycle_2.legacy_pinned is False
    assert cycle_2.activated is False
    assert all(not config.activated for config in CYCLE_CONFIGS.values())


def test_load_activated_cycle_refuses_cycle_1_and_cycle_2() -> None:
    with pytest.raises(CycleConfigNotActivatedError, match="legacy-pinned"):
        load_activated_cycle(CYCLE_1_ID)
    with pytest.raises(CycleConfigNotActivatedError, match=r"dn9\.2"):
        load_activated_cycle(CYCLE_2_ID)
    with pytest.raises(UnknownCycleConfigError, match="unknown cycle config"):
        load_cycle("cycle-9")


def test_cycle_1_documents_live_values_without_becoming_authority() -> None:
    cycle_1 = load_cycle(CYCLE_1_ID)

    assert (
        cycle_1.evaluation_registry.path == "model_registries/cycle-1-2026-06-30.json"
    )
    assert cycle_1.per_document_price_cap.reservation_usd == usd("3.05")
    assert cycle_1.per_document_price_cap.pacer_document_cap_usd == usd("3.00")
    assert cycle_1.free_first.required is True
    assert cycle_1.cohort_policy.schema_version == "legalforecast.cohort_policy.v3"
    assert cycle_1.spend.hard_cap_usd == usd("567.30")
    assert [key.attribute for key in cycle_1.ranking.keys] == [
        "missing_core_document_count",
        "estimated_cost_usd",
        "candidate_id",
    ]
    assert cycle_1.pointers
    assert (
        cycle_1.selector_model_policy.primary.registry_key == "google:gemini-3.5-flash"
    )


def test_cycle_2_draft_names_dn9_2_selectors_and_max_cost_ranking() -> None:
    cycle_2 = load_cycle(CYCLE_2_ID)
    policy = cycle_2.selector_model_policy

    assert policy.primary.registry_key == "openai:gpt-5.6-luna"
    assert [model.registry_key for model in policy.alternates] == [
        "anthropic:claude-sonnet-5",
        "google:gemini-3.5-flash",
    ]
    assert [key.attribute for key in cycle_2.ranking.keys] == [
        "max_cost",
        "min_cost",
        "candidate_id",
    ]
    assert cycle_2.ranking.record_cost_rank_in_provenance is True
    assert cycle_2.stratification.enabled is False
    assert cycle_2.stratification.bottom_decile_share_cap == usd("0.10")
    assert (
        cycle_2.document_need_buckets.text_for(DocumentNeedBucket.CLEARLY_REQUIRED)
        != ""
    )


def test_cycle_1_selector_preflight_passes_against_pinned_eval_registry() -> None:
    registry = preflight_selector_models(
        load_cycle(CYCLE_1_ID), repository_root_path=ROOT
    )

    assert {entry.registry_key for entry in registry.entries} == {
        "anthropic:claude-sonnet-5",
        "openai:gpt-5.6-luna",
        "openai:gpt-5.6-sol",
        "openai:gpt-5.6-terra",
    }


def test_cycle_2_preflight_refuses_missing_sentinel_registry() -> None:
    with pytest.raises(EvaluationRegistryPinError, match="no side-channel"):
        preflight_selector_models(load_cycle(CYCLE_2_ID), repository_root_path=ROOT)


def test_preflight_refuses_registry_model_in_selector_policy(tmp_path: Path) -> None:
    config = replace(
        load_cycle(CYCLE_2_ID),
        evaluation_registry=EvaluationRegistryPin(path=str(CYCLE_1_REGISTRY)),
        activation_blocker="test fixture",
    )

    with pytest.raises(SelectorRegistryCollisionError, match=r"openai:gpt-5\.6-luna"):
        preflight_selector_models(config, repository_root_path=ROOT)


def test_preflight_does_not_collide_on_same_model_id_from_another_provider(
    tmp_path: Path,
) -> None:
    source = json.loads(CYCLE_1_REGISTRY.read_text(encoding="utf-8"))
    record = dict(source[0])
    record["provider"] = "google"
    record["model_id"] = "gpt-5.6-luna"
    record["model_version_or_snapshot"] = "gpt-5.6-luna"
    record["display_name"] = "gpt-5.6-luna"
    registry_path = tmp_path / "eval-registry.json"
    registry_path.write_bytes(json.dumps([record]).encode("utf-8"))
    config = replace(
        load_cycle(CYCLE_2_ID),
        evaluation_registry=EvaluationRegistryPin(path=str(registry_path)),
        activation_blocker="test fixture",
    )

    registry = preflight_selector_models(config, repository_root_path=ROOT)

    assert {entry.registry_key for entry in registry.entries} == {"google:gpt-5.6-luna"}


def test_preflight_accepts_disjoint_fixture_registry(tmp_path: Path) -> None:
    registry_path = tmp_path / "eval-registry.json"
    registry_path.write_bytes(_registry_bytes("gpt-5.4-mini-2026-03-17"))
    config = replace(
        load_cycle(CYCLE_2_ID),
        evaluation_registry=EvaluationRegistryPin(path=str(registry_path)),
        activation_blocker="test fixture",
    )

    registry = preflight_selector_models(config, repository_root_path=ROOT)

    assert [entry.model_id for entry in registry.entries] == ["gpt-5.4-mini-2026-03-17"]


def test_preflight_uses_only_the_cycle_config_pin(tmp_path: Path) -> None:
    config = replace(
        load_cycle(CYCLE_1_ID),
        evaluation_registry=EvaluationRegistryPin(
            path=str(tmp_path / "does-not-exist.json")
        ),
        activation_blocker="test fixture",
        legacy_pinned=True,
        activated=False,
    )

    with pytest.raises(EvaluationRegistryPinError, match=r"does-not-exist\.json"):
        preflight_selector_models(config, repository_root_path=ROOT)


def test_preflight_refuses_hash_mismatch(tmp_path: Path) -> None:
    registry_path = tmp_path / "eval-registry.json"
    registry_path.write_bytes(_registry_bytes("other-model"))
    config = replace(
        load_cycle(CYCLE_1_ID),
        evaluation_registry=EvaluationRegistryPin(
            path=str(registry_path),
            sha256="0" * 64,
        ),
        activation_blocker="test fixture",
    )

    with pytest.raises(EvaluationRegistryPinError, match="SHA-256"):
        preflight_selector_models(config, repository_root_path=ROOT)


def test_require_activated_accepts_explicit_fixture(tmp_path: Path) -> None:
    registry_path = tmp_path / "eval-registry.json"
    registry_path.write_bytes(_registry_bytes("other-model"))
    config = replace(
        load_cycle(CYCLE_2_ID),
        activated=True,
        activation_blocker=None,
        evaluation_registry=EvaluationRegistryPin(path=str(registry_path)),
        selector_model_policy=SelectorModelPolicy(
            primary=SelectorModel(
                provider="anthropic",
                model_id="claude-haiku-4-5-20251001",
                model_version_or_snapshot="claude-haiku-4-5-20251001",
            ),
            alternates=(),
        ),
    )

    assert require_activated(config) is config
    preflight_selector_models(config, repository_root_path=ROOT)


def test_duplicate_selector_keys_fail_at_construction() -> None:
    with pytest.raises(CycleConfigError, match="duplicate registry keys"):
        SelectorModelPolicy(
            primary=SelectorModel(
                provider="openai",
                model_id="gpt-5.6-luna",
                model_version_or_snapshot="gpt-5.6-luna",
            ),
            alternates=(
                SelectorModel(
                    provider="openai",
                    model_id="gpt-5.6-luna",
                    model_version_or_snapshot="gpt-5.6-luna",
                ),
            ),
        )


def test_selector_model_rejects_mutable_latest_or_preview_alias() -> None:
    with pytest.raises(CycleConfigError, match="preview/latest"):
        SelectorModel(
            provider="google",
            model_id="gemini-flash-latest",
            model_version_or_snapshot="gemini-flash-latest",
        )
    with pytest.raises(CycleConfigError, match="preview/latest"):
        SelectorModel(
            provider="anthropic",
            model_id="claude-sonnet-5",
            model_version_or_snapshot="claude-sonnet-5-preview",
        )


def test_stratification_cap_must_be_a_share() -> None:
    with pytest.raises(CycleConfigError, match="bottom_decile_share_cap"):
        StratificationPolicy(enabled=True, bottom_decile_share_cap=usd("1.10"))


def test_repository_root_is_the_worktree() -> None:
    assert (repository_root() / "legalforecast" / "config" / "__init__.py").is_file()
    assert load_model_registry(CYCLE_1_REGISTRY).entries


def test_public_record_is_json_serializable() -> None:
    payload = json.dumps(dict(load_cycle(CYCLE_2_ID).as_public_record()))

    assert "gpt-5.6-luna" in payload
    assert '"activated": false' in payload


def _registry_bytes(model_id: str) -> bytes:
    source = json.loads(CYCLE_1_REGISTRY.read_text(encoding="utf-8"))
    record = dict(source[0])
    record["provider"] = "openai"
    record["model_id"] = model_id
    record["model_version_or_snapshot"] = model_id
    record["display_name"] = model_id
    return json.dumps([record]).encode("utf-8")
