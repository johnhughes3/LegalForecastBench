"""Synthetic cap observations bind policy and credentials, never prove a live cap."""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

import pytest
from legalforecast.multiharness.auth_profiles import resolve_auth_profile
from legalforecast.multiharness.local_cli_environment import StaticCredentialSource
from legalforecast.multiharness.provider_spend_cap import (
    CapBoundCredentialSource,
    ProviderCapError,
    ProviderSpendCap,
)
from legalforecast.multiharness.spend import (
    InvocationBudget,
    SpendController,
    SpendPolicy,
    SpendSettlementError,
    UsageObservation,
)
from tests.test_multiharness_spend import _call, _policy, _pricing, _solver_cap


def test_recorded_owner_words_need_no_signing_authority(tmp_path: Path) -> None:
    from legalforecast.multiharness.tier0_runner import load_detached_approval

    path = tmp_path / "approval.json"
    record = {
        "spec_sha256": "sha256:" + "a" * 64,
        "owner_approval": "Billing fixed, proceed with this bounded run.",
        "max_cost_usd": "25.000000",
    }
    path.write_text(json.dumps(record))
    approval = load_detached_approval(path, spec_sha256=record["spec_sha256"])
    from legalforecast.multiharness.tier0_runner import RecordedOwnerApproval

    assert isinstance(approval, RecordedOwnerApproval)
    assert approval.to_record() == record
    approval.validate_ceiling("25.000000")
    with pytest.raises(ValueError, match="ceiling"):
        approval.validate_ceiling("25.000001")


KEY = "synthetic-capped-key"


def _cap(**overrides: object) -> ProviderSpendCap:
    now = datetime.now(UTC)
    record: dict[str, object] = {
        "provider": "provider-a",
        "auth_profile": "published-api-key",
        "credential_env_var": "ANTHROPIC_API_KEY",
        "credential_sha256": sha256(KEY.encode()).hexdigest(),
        "hard_limit_usd": "0.003000",
        "observed_at": now.isoformat(),
        "enforced_until": (now + timedelta(hours=1)).isoformat(),
        "enforcement": "hard_stop_no_auto_recharge",
        "evidence_reference": "synthetic-provider-cap-observation",
    }
    return ProviderSpendCap.from_record(record | overrides)


def _stale_cap() -> ProviderSpendCap:
    return _cap(
        provider="anthropic",
        hard_limit_usd="8.000000",
        observed_at="2000-01-01T00:00:00+00:00",
        enforced_until="2000-01-01T01:00:00+00:00",
    )


def test_stale_cap_remints_identical_artifact_bytes_and_hashes(tmp_path: Path) -> None:
    from legalforecast.multiharness.tier0_mint import mint_tier0_artifacts
    from tests.test_tier0_operator_half import CRITERION_IDS, _native_thin

    minted = []
    for directory in ("original", "remint"):
        output_dir = tmp_path / directory
        output_dir.mkdir()
        native = replace(
            _native_thin(),
            budget_argument=None,
            command=("harvey-lab-thin", "--task", "fixture"),
            provider_cap=_stale_cap(),
        )
        minted.append(
            mint_tier0_artifacts(
                output_dir, criterion_ids=CRITERION_IDS, native_thin=native
            )
        )
    original, remint = minted
    for field in ("spec_path", "pricing_path", "policy_path"):
        assert (
            getattr(original, field).read_bytes() == getattr(remint, field).read_bytes()
        )
    assert original.spec_sha256 == remint.spec_sha256
    assert original.pricing_snapshot_sha256 == remint.pricing_snapshot_sha256
    assert original.spend_policy_sha256 == remint.spend_policy_sha256
    assert _stale_cap().observed_at in original.policy_path.read_text()


def test_runtime_refuses_stale_cap_before_credentials_or_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import legalforecast.multiharness.local_cli_runtime as runtime
    from tests.test_multiharness_local_cli_runtime import _spec, _write_script

    class ForbiddenCredentials(StaticCredentialSource):
        def fetch_projected_env(self, profile: object) -> dict[str, str]:
            pytest.fail("stale cap must refuse before fetching credentials")

    def forbidden_process(*args: object, **kwargs: object) -> None:
        pytest.fail("stale cap must refuse before starting a process")

    monkeypatch.setattr(runtime.subprocess, "Popen", forbidden_process)
    cap = _stale_cap()
    spec = _spec(
        tmp_path,
        script=_write_script(tmp_path, "raise AssertionError('must not launch')"),
        auth_profile=cap.auth_profile,
        supported=(cap.auth_profile,),
        profile_env_vars=((cap.auth_profile, (cap.credential_env_var,)),),
    )
    with pytest.raises(ProviderCapError, match="within 15 minutes"):
        runtime.execute_local_cli(
            spec,
            tmp_path / "scratch",
            credential_source=CapBoundCredentialSource(
                cap, ForbiddenCredentials({}), 300
            ),
            parent_env={"PATH": "/usr/bin"},
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"enforcement": "soft_alert"},
        {"hard_limit_usd": "NaN"},
        {"credential_sha256": "unknown"},
        {"evidence_reference": ""},
        {"unknown": True},
    ],
)
def test_invalid_cap_observation_is_refused(changes: dict[str, object]) -> None:
    with pytest.raises(ProviderCapError):
        _cap(**changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"hard_limit_usd": "1"},
        {"provider": "wrong-provider"},
        {"observed_at": (datetime.now(UTC) - timedelta(days=1)).isoformat()},
        {"enforced_until": (datetime.now(UTC) + timedelta(seconds=10)).isoformat()},
    ],
)
def test_cap_must_cover_exact_provider_ceiling_and_run_window(
    changes: dict[str, object],
) -> None:
    with pytest.raises(ProviderCapError):
        _cap(**changes).validate_for_run(
            provider="provider-a",
            auth_profile="published-api-key",
            max_cost_usd="0.003000",
            timeout_seconds=300,
        )


def test_cap_bound_credential_source_refuses_rotated_or_extra_keys() -> None:
    profile = resolve_auth_profile(
        "published-api-key",
        supported_profiles=("published-api-key",),
        projected_env_vars=("ANTHROPIC_API_KEY",),
    )
    cap = _cap()
    source = CapBoundCredentialSource(
        cap, StaticCredentialSource({"ANTHROPIC_API_KEY": KEY}), 300
    )
    assert source.fetch_projected_env(profile) == {"ANTHROPIC_API_KEY": KEY}
    rotated = CapBoundCredentialSource(
        cap, StaticCredentialSource({"ANTHROPIC_API_KEY": "rotated"}), 300
    )
    with pytest.raises(ProviderCapError, match="credential"):
        rotated.fetch_projected_env(profile)


def test_cap_round_trip_and_overrun_are_preserved_in_spend_journal() -> None:
    solver = replace(
        _solver_cap(),
        invocation_budget=InvocationBudget(mode="provider_cap", provider_cap=_cap()),
    )
    policy = _policy(solver=solver)
    restored = SpendPolicy.from_record(policy.to_record())
    assert restored.policy_sha256 == policy.policy_sha256
    assert (
        restored.solver_for("arm-a").invocation_budget.provider_cap
        == solver.invocation_budget.provider_cap
    )
    controller = SpendController(restored, _pricing())
    reservation = controller.reserve(_call("first"))
    with pytest.raises(SpendSettlementError):
        controller.settle(
            reservation,
            UsageObservation(
                basis="provider_reported",
                pricing_snapshot_sha256=_pricing().snapshot_sha256,
                input_tokens=100,
                output_tokens=100,
                reported_cost_usd="0.004000",
            ),
        )
    assert controller.terminal
    assert controller.archive_record()["events"]


def test_provider_cap_does_not_fabricate_unknown_usage() -> None:
    solver = replace(
        _solver_cap(),
        invocation_budget=InvocationBudget(mode="provider_cap", provider_cap=_cap()),
    )
    controller = SpendController(_policy(solver=solver), _pricing())
    reservation = controller.reserve(_call("unknown-usage"))
    with pytest.raises(SpendSettlementError):
        controller.settle(
            reservation, UsageObservation.unknown("native metrics absent")
        )
    assert controller.terminal
    assert controller.archive_record()["events"]


def test_cap_mint_round_trip_does_not_invent_a_budget_flag(tmp_path: Path) -> None:
    from legalforecast.multiharness.tier0_mint import mint_tier0_artifacts
    from legalforecast.multiharness.tier0_runner import (
        load_executable_spec,
        load_spend_artifacts,
    )
    from tests.test_tier0_operator_half import CRITERION_IDS, _native_thin

    native = replace(
        _native_thin(),
        budget_argument=None,
        command=("harvey-lab-thin", "--task", "fixture"),
        provider_cap=_cap(provider="anthropic", hard_limit_usd="8.000000"),
    )
    minted = mint_tier0_artifacts(
        tmp_path, criterion_ids=CRITERION_IDS, native_thin=native
    )
    spec, _ = load_executable_spec(minted.spec_path, minted.spec_sha256)
    policy, pricing = load_spend_artifacts(minted.spec_path, spec)
    caps = [item.invocation_budget for item in policy.solver_ceilings]
    assert sum(item.mode == "provider_cap" for item in caps) == 1
    assert (
        next(item for item in caps if item.mode == "provider_cap").provider_cap
        == native.provider_cap
    )
    from legalforecast.multiharness.adapter_registry import HARVEY_LAB_REGISTRY_NAME
    from legalforecast.multiharness.tier0_runner import (
        Tier0RunnerError,
        _solver_ceiling,
    )

    native_arm = next(
        arm for arm in spec.arms if arm.adapter == HARVEY_LAB_REGISTRY_NAME
    )
    with pytest.raises(Tier0RunnerError, match="native usage accounting"):
        _solver_ceiling(SpendController(policy, pricing), native_arm)


def test_owner_note_does_not_bypass_missing_evaluator_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import legalforecast.multiharness.cli as cli
    from legalforecast.cli import main
    from tests.test_multiharness_tier0_runner import (
        _install_fixture_binaries,
        _run_args,
        _write_spec_and_approval,
    )

    env = _install_fixture_binaries(tmp_path)
    monkeypatch.setenv("PATH", env["PATH"])
    spec, approval, digest = _write_spec_and_approval(tmp_path, env)
    approval.write_text(
        json.dumps(
            {"spec_sha256": digest, "owner_approval": "Proceed", "max_cost_usd": "25"}
        )
    )

    def obsolete_loader() -> None:
        pytest.fail("ordinary owner approval must not load the human signing key")

    monkeypatch.setattr(cli, "load_approved_tier0_approval_authority", obsolete_loader)
    assert main(_run_args(spec, approval, spec_sha256=digest)) == 2
    assert not (tmp_path / "private").exists()
