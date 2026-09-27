"""Provider-free tests of OpenClaw's protected descriptor and spend boundary."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import legalforecast.multiharness.openclaw_container as openclaw_container
import pytest
from legalforecast._json_io import write_json_object
from legalforecast.evals.provider_spend_control import (
    FrozenAttemptPolicy,
    ProviderCapExceededError,
    SqliteProviderSpendAuthority,
)
from legalforecast.multiharness.auth_profiles import PUBLISHED_API_KEY
from legalforecast.multiharness.claude_code_container import (
    ClaudeCodeContainerAdapterError,
)
from legalforecast.multiharness.container_harness import (
    ContainerHarnessResult,
    ContainerHarnessSpec,
)
from legalforecast.multiharness.container_harness.fence import unobservable_fence
from legalforecast.multiharness.container_harness.model_gateway_paid import (
    load_paid_gateway_config,
)
from legalforecast.multiharness.container_harness.model_gateway_plan import (
    MODEL_GATEWAY_PROTECTED_UPSTREAM_BASE_URL,
)
from legalforecast.multiharness.container_harness.model_gateway_protocol import (
    AnthropicModelGateway,
)
from legalforecast.multiharness.openclaw import (
    GATEWAY_HARNESS_ID,
    OpenClawError,
    normalize_result,
    record_digest,
)
from legalforecast.multiharness.openclaw_container import OpenClawContainerAdapter
from legalforecast.multiharness.openclaw_worker import CAPABILITY_ENV
from legalforecast.multiharness.paid_gateway_descriptor import (
    TERMINAL_HARNESS_ID,
    ProtectedPaidGatewayDescriptor,
    issue_paid_gateway_descriptor,
    write_paid_gateway_descriptor,
)
from legalforecast.multiharness.protected_terminal_paid import (
    ProtectedTerminalPaidError,
    ProtectedTerminalSpendConfig,
    ProviderGatewaySpendController,
    anthropic_registry_charge_extractor,
)
from legalforecast.multiharness.release_harness import (
    RELEASE_FORECAST_OUTPUT_ARTIFACT_ID,
    RELEASE_HARNESS_TRANSCRIPT_ARTIFACT_ID,
    release_bytes_sha256,
)
from legalforecast.multiharness.spec import RunRequest
from legalforecast.multiharness.terminal_release import build_terminal_release_adapter
from legalforecast.multiharness.terminal_release_cli import TerminalReleaseOptions
from legalforecast.release import load_forecast_run_inputs

from test_container_model_gateway_spend import _FakeUpstream, _message_body, _policy
from test_multiharness_openclaw import envelope, request
from test_paid_gateway_descriptor import _CEILING_MICROUSD, _ENVIRONMENT, _inputs
from test_protected_terminal_paid import _config, _registry_entry


def _issued_options(
    tmp_path: Path,
    *,
    harness_id: str = GATEWAY_HARNESS_ID,
    reasoning_effort: str | None = "high",
) -> tuple[TerminalReleaseOptions, ProtectedPaidGatewayDescriptor]:
    manifest, forecast, artifacts, registry = _inputs(tmp_path)
    records = json.loads(registry.read_text())
    records[0]["model_id"] = "claude-opus-5-5"
    records[0]["model_version_or_snapshot"] = "claude-opus-5-5"
    if reasoning_effort is not None:
        records[0]["reasoning_effort"] = reasoning_effort
    registry.write_text(json.dumps(records))
    descriptor = issue_paid_gateway_descriptor(
        manifest_path=manifest,
        forecast_path=forecast,
        artifact_root=artifacts,
        model_registry_path=registry,
        model_key="anthropic:claude-opus-5-5",
        ceiling_microusd=_CEILING_MICROUSD,
        account="official",
        environment=_ENVIRONMENT,
        harness_id=harness_id,
    )
    paid_config = tmp_path / "paid-gateway.json"
    write_paid_gateway_descriptor(paid_config, descriptor)
    return TerminalReleaseOptions(
        forecast_release=forecast,
        labels_release=None,
        artifact_root=artifacts,
        output_dir=tmp_path / "output",
        model_key=descriptor.model_key,
        image="openclaw@sha256:" + "1" * 64,
        auth_profile=PUBLISHED_API_KEY,
        max_budget_usd=_CEILING_MICROUSD / 1_000_000,
        approval_reference=None,
        fixture_base_url=None,
        fixture_egress_network=None,
        backend="docker",
        timeout_seconds=30,
        run_id="openclaw-test",
        paid_config_path=paid_config,
        model_registry_path=registry,
        gateway_upstream_base_url=MODEL_GATEWAY_PROTECTED_UPSTREAM_BASE_URL,
        gateway_image_digest="gateway@sha256:" + "2" * 64,
        harness="openclaw",
    ), descriptor


@pytest.fixture
def protected_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in _ENVIRONMENT.items():
        monkeypatch.setenv(key, value)


def test_openclaw_descriptor_binds_runtime_release_and_distinct_spend_identity(
    tmp_path: Path, protected_environment: None
) -> None:
    options, descriptor = _issued_options(tmp_path)
    assert options.paid_config_path is not None
    assert options.model_registry_path is not None
    loaded = load_paid_gateway_config(
        options.paid_config_path, model_registry_path=options.model_registry_path
    )
    inputs = load_forecast_run_inputs(
        options.artifact_root / "run-manifest.json",
        options.forecast_release,
        artifact_root=options.artifact_root,
    )
    claude = issue_paid_gateway_descriptor(
        manifest_path=options.artifact_root / "run-manifest.json",
        forecast_path=options.forecast_release,
        artifact_root=options.artifact_root,
        model_registry_path=options.model_registry_path,
        model_key=options.model_key,
        ceiling_microusd=_CEILING_MICROUSD,
        account="official",
        environment=_ENVIRONMENT,
    )
    assert loaded.harness_id == descriptor.harness_id == GATEWAY_HARNESS_ID
    assert claude.to_record()["harness_id"] == TERMINAL_HARNESS_ID
    assert loaded.forecast_release_digest == inputs.execution.release.release_digest
    assert loaded.spend.authority_identity_sha256 != claude.authority_identity_sha256
    assert descriptor.reservation_ledger_sha256 != claude.reservation_ledger_sha256
    assert loaded.spend.ceiling_microusd == claude.ceiling_microusd
    assert loaded.max_requests == 64
    assert OpenClawContainerAdapter(options).options == options


def test_descriptor_issuer_rejects_unrecognized_harness(tmp_path: Path) -> None:
    with pytest.raises(ProtectedTerminalPaidError, match=r"unsupported.*harness"):
        _issued_options(tmp_path, harness_id="openclaw-unpinned")


def test_claude_selection_refuses_openclaw_paid_descriptor(
    tmp_path: Path, protected_environment: None
) -> None:
    options, _ = _issued_options(tmp_path)
    with pytest.raises(ClaudeCodeContainerAdapterError, match="harness"):
        build_terminal_release_adapter(
            replace(
                options, harness="claude-code-terminal", image="sha256:" + "1" * 64
            ),
            case_count=1,
        )
    assert not options.output_dir.exists()


@pytest.mark.parametrize(
    "harness,reasoning,match",
    [
        (TERMINAL_HARNESS_ID, "high", "exact pinned OpenClaw"),
        (GATEWAY_HARNESS_ID, None, "explicit high reasoning"),
    ],
)
def test_container_refuses_unbound_descriptor_or_implicit_reasoning(
    tmp_path: Path,
    protected_environment: None,
    harness: str,
    reasoning: str | None,
    match: str,
) -> None:
    options, _ = _issued_options(
        tmp_path, harness_id=harness, reasoning_effort=reasoning
    )
    with pytest.raises(OpenClawError, match=match):
        OpenClawContainerAdapter(options)


@pytest.mark.parametrize(
    "change,match",
    [
        ({"auth_profile": "fixture-none"}, "protected paid descriptor"),
        ({"paid_config_path": None}, "protected paid descriptor"),
        ({"fixture_base_url": "http://fixture"}, "fixture routing"),
        ({"gateway_upstream_base_url": "https://other.example"}, "fixed Anthropic"),
        ({"model_key": "anthropic:other"}, "model must match"),
        ({"max_budget_usd": 301.0}, "ceiling must equal"),
    ],
)
def test_container_refuses_changed_paid_route_before_launch(
    tmp_path: Path,
    protected_environment: None,
    change: dict[str, object],
    match: str,
) -> None:
    options, _ = _issued_options(tmp_path)
    with pytest.raises(OpenClawError, match=match):
        OpenClawContainerAdapter(replace(options, **change))
    assert not options.output_dir.exists()


def _release_request(descriptor: ProtectedPaidGatewayDescriptor) -> RunRequest:
    original = request()
    return replace(
        original,
        model_key=descriptor.model_key,
        sandbox_policy=replace(original.sandbox_policy, allowed_provider_env_vars=()),
        task=replace(
            original.task,
            metadata={
                **original.task.metadata,
                "forecast_release_digest": descriptor.forecast_release_digest,
            },
        ),
    )


@pytest.mark.parametrize("mismatch", ["model", "grant", "release"])
def test_container_rejects_request_mismatch_before_staging_or_launch(
    tmp_path: Path, protected_environment: None, mismatch: str
) -> None:
    options, descriptor = _issued_options(tmp_path)
    adapter = OpenClawContainerAdapter(options)
    run_request = _release_request(descriptor)
    if mismatch == "model":
        run_request = replace(run_request, model_key="anthropic:other")
    elif mismatch == "grant":
        run_request = replace(
            run_request,
            sandbox_policy=replace(
                run_request.sandbox_policy,
                allowed_provider_env_vars=("ANTHROPIC_API_KEY",),
            ),
        )
    else:
        run_request = replace(
            run_request,
            task=replace(
                run_request.task,
                metadata={"forecast_release_digest": "sha256:" + "0" * 64},
            ),
        )
    workspace = tmp_path / "worker"
    with pytest.raises(OpenClawError, match="differs from"):
        adapter.run_with_solver_input(run_request, workspace, tmp_path / "absent")
    assert not workspace.exists()


def _sqlite_authority(
    tmp_path: Path, config: ProtectedTerminalSpendConfig
) -> SqliteProviderSpendAuthority:
    return SqliteProviderSpendAuthority(
        tmp_path / "spend.sqlite",
        authority_identity_sha256=config.authority_identity_sha256,
        cycle_id=config.cycle_id,
        provider="anthropic",
        account=config.account,
        cap_microusd=config.ceiling_microusd,
        policy=FrozenAttemptPolicy(
            reservation_ledger_sha256=config.reservation_ledger_sha256,
            max_billable_attempts=1,
            failure_threshold=10,
            failure_window_seconds=60,
        ),
    )


@pytest.mark.parametrize("complete_usage", [True, False])
def test_sqlite_admission_and_settlement_of_native_gateway_usage(
    tmp_path: Path, complete_usage: bool
) -> None:
    """Real accounting components; SQLite lacks the protected transport marker."""
    config = replace(_config(), ceiling_microusd=300)
    authority = _sqlite_authority(tmp_path, config)
    usage = {"input_tokens": 10, "output_tokens": 2}
    if complete_usage:
        usage.update(cache_creation_input_tokens=4, cache_read_input_tokens=6)
    upstream = _FakeUpstream(json.dumps({"usage": usage}).encode())
    try:
        controller = ProviderGatewaySpendController(
            authority=authority,
            config=config,
            reservation_microusd=200,
            charge_extractor=anthropic_registry_charge_extractor(
                _registry_entry("claude-fixture")
            ),
        )
        gateway = AnthropicModelGateway(_policy(upstream))
        unauthenticated = gateway.handle(_message_body(), api_key="wrong")
        assert unauthenticated.status_code == 401
        assert authority.snapshot().attempt_count == 0
        assert upstream.requests == []
        lease = controller.authorize_request(
            request_id="openclaw-case-1",
            body=_message_body(),
            model="claude-fixture",
            max_tokens=4,
        )
        assert authority.snapshot().committed_microusd == 200
        assert authority.snapshot().reserved_attempt_count == 1
        first = gateway.handle(_message_body(), api_key="run-capability-sentinel")
        observed = gateway.usage.snapshot()
        settled = controller.settle_response(
            lease,
            response_body=first.body,
            response_status=first.status_code,
            content_type=first.headers["content-type"],
            input_tokens=observed.observed_input_tokens,
            output_tokens=observed.observed_output_tokens,
        )
        snapshot = authority.snapshot()
        assert first.status_code == 200
        assert settled is complete_usage
        assert snapshot.attempt_count == 1
        assert snapshot.reserved_attempt_count == 0
        assert snapshot.settled_attempt_count == int(complete_usage)
        assert snapshot.ambiguous_attempt_count == int(not complete_usage)
        # Prices per million: 10*5 + 2*25 + 4*6.25 + 6*.5 = 128 micro-USD.
        assert snapshot.committed_microusd == (128 if complete_usage else 200)
        with pytest.raises(ProviderCapExceededError):
            controller.authorize_request(
                request_id="openclaw-case-1",
                body=_message_body(),
                model="claude-fixture",
                max_tokens=4,
            )
        assert authority.snapshot() == snapshot
        assert len(upstream.requests) == 1
    finally:
        upstream.close()
        authority.close()


def test_gateway_refuses_authority_without_durable_transport_marker(
    tmp_path: Path,
) -> None:
    config = replace(_config(), ceiling_microusd=300)
    authority = _sqlite_authority(tmp_path, config)
    upstream = _FakeUpstream(b"must not be requested")
    try:
        gateway = AnthropicModelGateway(
            _policy(upstream),
            spend_controller=ProviderGatewaySpendController(
                authority=authority,
                config=config,
                reservation_microusd=200,
                charge_extractor=anthropic_registry_charge_extractor(
                    _registry_entry("claude-fixture")
                ),
            ),
            request_id="openclaw-case-1",
        )
        response = gateway.handle(_message_body(), api_key="run-capability-sentinel")
        assert response.status_code == 503
        assert b"spend authorization failed" in response.body
        assert upstream.requests == []
        snapshot = authority.snapshot()
        assert snapshot.attempt_count == 1
        assert snapshot.ambiguous_attempt_count == 1
        assert snapshot.settled_attempt_count == 0
        assert snapshot.committed_microusd == 200
    finally:
        upstream.close()
        authority.close()


@pytest.mark.parametrize("drift", [None, "openclaw_version", "served_model"])
def test_host_normalizes_worker_output_and_binds_protected_container_spec(
    tmp_path: Path,
    protected_environment: None,
    monkeypatch: pytest.MonkeyPatch,
    drift: str | None,
) -> None:
    """Host component test: container return is a double, not Docker evidence."""
    options, descriptor = _issued_options(tmp_path)
    adapter = OpenClawContainerAdapter(options)
    solver = tmp_path / "solver"
    solver.mkdir()
    prompt = b"Outcome-blinded case record and unit count-1."
    (solver / "prompt.txt").write_bytes(prompt)
    original = _release_request(descriptor)
    run_request = replace(
        original,
        task=replace(
            original.task,
            metadata={
                **original.task.metadata,
                "prompt_sha256": release_bytes_sha256(prompt),
                "packet_sha256": "sha256:" + "4" * 64,
            },
        ),
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ambient-key-must-not-reach-worker")
    launches: list[ContainerHarnessSpec] = []

    def container_double(
        spec: ContainerHarnessSpec, *, publication_directory: Path, backend: str
    ) -> ContainerHarnessResult:
        launches.append(spec)
        assert backend == options.backend
        assert (
            publication_directory == spec.workspace / "private-logs/container-package"
        )
        assert spec.image == options.image
        assert spec.proxy_image == options.gateway_image_digest
        assert spec.cli_name == "openclaw" and spec.harness_argv == ("run",)
        assert spec.read_only_workspace_paths == (
            "prompt.txt",
            "openclaw-request.json",
            "openclaw-model.json",
        )
        assert (spec.workspace / "prompt.txt").read_bytes() == prompt
        assert (spec.workspace / "prompt.txt").stat().st_mode & 0o777 == 0o400
        assert (
            json.loads((spec.workspace / "openclaw-request.json").read_text())
            == run_request.to_record()
        )
        assert set(spec.environment) == {CAPABILITY_ENV}
        assert "ambient-key" not in repr(spec.environment)
        gateway = spec.model_gateway
        assert gateway is not None
        assert gateway.run_capability == spec.environment[CAPABILITY_ENV]
        assert gateway.model_key == run_request.model_key
        assert gateway.request_id == run_request.request_id
        assert gateway.paid_config_path == options.paid_config_path
        assert gateway.model_registry_path == options.model_registry_path
        assert gateway.upstream_base_url == MODEL_GATEWAY_PROTECTED_UPSTREAM_BASE_URL
        worker = normalize_result(
            run_request,
            spec.workspace,
            {**envelope(), "provider": "anthropic", "model": "claude-opus-5-5"},
            tool_reads=2,
            prompt_complete=True,
            gateway_auth=True,
        )
        if drift is not None:
            worker = replace(
                worker,
                public_summary={**worker.public_summary, drift: "unexpected"},
            )
        write_json_object(spec.workspace / "openclaw-result.json", worker.to_record())
        return ContainerHarnessResult(
            run_id=spec.run_id,
            exit_code=0,
            timed_out=False,
            duration_seconds=1,
            stdout_path=spec.log_root / "stdout",
            stderr_path=spec.log_root / "stderr",
            image_id="sha256:" + "1" * 64,
            proxy_image_id="sha256:" + "2" * 64,
            allowed_hosts=spec.allow_hosts,
            refused=(),
            allowlist={},
            fence=unobservable_fence(source="unobservable"),
            gateway_usage={"request_count": 2, "rejected_count": 0},
        )

    monkeypatch.setattr(openclaw_container, "run_container_harness", container_double)
    workspace = tmp_path / "worker"
    if drift is not None:
        with pytest.raises(OpenClawError, match="result/provenance mismatch"):
            adapter.run_with_solver_input(run_request, workspace, solver)
        assert not (workspace / "private-logs/release-harness-transcript.json").exists()
        return
    result = adapter.run_with_solver_input(run_request, workspace, solver)
    assert len(launches) == 1
    forecast, transcript_artifact = result.artifacts
    assert (forecast.artifact_id, transcript_artifact.artifact_id) == (
        RELEASE_FORECAST_OUTPUT_ARTIFACT_ID,
        RELEASE_HARNESS_TRANSCRIPT_ARTIFACT_ID,
    )
    for artifact in result.artifacts:
        data = (workspace / artifact.path).read_bytes()
        assert artifact.sha256 == release_bytes_sha256(data)
        assert artifact.size_bytes == len(data)
        assert artifact.public is False
    transcript = json.loads((workspace / transcript_artifact.path).read_text())
    assert transcript["request_sha256"] == run_request.request_sha256
    assert transcript["prompt_sha256"] == release_bytes_sha256(prompt)
    assert transcript["packet_sha256"] == run_request.task.metadata["packet_sha256"]
    assert transcript["response_sha256"] == forecast.sha256
    assert result.public_summary["transcript_sha256"] == transcript_artifact.sha256
    assert result.result_sha256 == record_digest(
        {
            "request": run_request.request_sha256,
            "summary": result.public_summary,
            "forecast": forecast.sha256,
        }
    )
