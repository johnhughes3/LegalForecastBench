"""The pre-dispatch authorization chain in explicit supplementary mode.

PR #1003 built the supplementary lane from the provider cell forward, and its
end-to-end test drove ``run_per_case_evaluation`` directly.  That is exactly why
the gap this file covers survived review: cost projection and execution-scope
issuance were never exercised, so nothing noticed that a sibling freeze could not
reach a paid dispatch at all.

Every test here therefore drives the *dispatch chain* -- the request contract, the
authenticator, the receipt, the workflow-environment entry point, the scope, and
and the workflow wiring -- rather than the runner.  Refusals are asserted in
both directions, because a lane that only fails one way can be entered from the
other.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from legalforecast.contracts.schemas import (
    MANIFEST_FREEZE_RUNTIME_CONTRACT_V1,
    MANIFEST_MODE_FORECAST_RUN_RECORD_V1,
)
from legalforecast.evals.corpus_manifest import cost_projector_auth as auth_module
from legalforecast.evals.corpus_manifest.cost_projector import (
    ManifestCostProjectionError,
    ManifestCostProjectionRequest,
    issue_manifest_cost_projection,
)
from legalforecast.evals.corpus_manifest.cost_projector_workflow import (
    issue_manifest_cost_projection_from_workflow_environment,
)
from legalforecast.evals.corpus_manifest.execution_scope import (
    ExecutionScopeError,
    issue_execution_plan_v4,
    issue_model_execution_scope,
    verify_execution_scope,
    verify_execution_scope_runtime,
)
from legalforecast.evals.corpus_manifest.records import registry_record
from legalforecast.evals.model_registry import (
    earliest_eligible_decision_date,
    load_model_registry,
    load_model_registry_bytes,
    require_official_registry_entries,
)
from legalforecast.protocol.freeze import (
    FreezeBundle,
    FrozenArtifact,
    FrozenArtifactName,
    write_hash_bundle,
)

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_REGISTRY = (
    ROOT
    / "model_registries"
    / "cycle-1-2026-06-30-claude-opus-4-8-successor-2026-08-21.json"
)
SUPPLEMENTARY_REGISTRY = (
    ROOT / "model_registries" / "cycle-1-supplementary-gemini-3.7-flash-2026-08-29.json"
)
SUPPLEMENTARY_MODEL_KEY = "google:gemini-3.7-flash"
OFFICIAL_MODEL_KEY = "openai:gpt-5.6-terra"
CYCLE_ID = "cycle-1"
CORPUS_ANCHOR = "2026-06-30"
MANIFEST_DIGEST = "a" * 64


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _write_json(path: Path, value: object) -> bytes:
    payload = _json_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return payload


class _Chain:
    """One official manifest run plus the sibling freeze built over it."""

    def __init__(
        self,
        *,
        root: Path,
        official_freeze: Path,
        sibling_freeze: Path,
        official_registry: Path,
        supplementary_registry: Path,
        run_inputs: Path,
    ) -> None:
        self.root = root
        self.official_freeze = official_freeze
        self.sibling_freeze = sibling_freeze
        self.official_registry = official_registry
        self.supplementary_registry = supplementary_registry
        self.run_inputs = run_inputs


def _freeze(
    path: Path,
    *,
    registry_path: Path,
    prompt_path: Path,
    manifest_path: Path,
    shared: dict[FrozenArtifactName, Path],
    caps_path: Path,
    policy_path: Path,
) -> FreezeBundle:
    """Write a real hash bundle over real artifact bytes.

    The bundle file is genuine -- ``load_freeze_bundle`` validates its own
    commitment hash, which is what the identity check reads.  Only the freeze
    protocol's *policy* validation is stubbed by the caller, because it is not
    what any test here is about.
    """

    selected = {
        FrozenArtifactName.MANIFEST: manifest_path,
        FrozenArtifactName.MODEL_REGISTRY: registry_path,
        FrozenArtifactName.PROMPT: prompt_path,
        FrozenArtifactName.PROVIDER_CYCLE_CAPS: caps_path,
        FrozenArtifactName.EXECUTION_POLICY: policy_path,
        **shared,
    }
    artifacts = [
        FrozenArtifact(
            name=name,
            path=selected[name],
            sha256=hashlib.sha256(selected[name].read_bytes()).hexdigest(),
            size_bytes=selected[name].stat().st_size,
        )
        for name in FrozenArtifactName
    ]
    bundle = FreezeBundle(
        cycle_id=CYCLE_ID,
        freeze_timestamp=datetime(2026, 8, 29, tzinfo=UTC),
        artifacts=tuple(artifacts),
    )
    write_hash_bundle(path, bundle)
    return bundle


def _chain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    sibling_registry_bytes: bytes | None = None,
    drift_shared_artifact: bool = False,
    decision_dates: list[str] | None = None,
) -> _Chain:
    """Build a real official freeze and a real sibling freeze over one corpus.

    Both bundles are written with the repository's own ``write_hash_bundle``, so
    the identity check runs against genuine freeze artifacts rather than a
    stand-in for one.
    """

    root = tmp_path / "chain"
    root.mkdir()
    manifest_path = root / "owner-manifest.json"
    manifest_bytes = _write_json(manifest_path, {"cycle_id": CYCLE_ID})

    official_registry_path = root / "official-registry.json"
    official_registry_bytes = OFFICIAL_REGISTRY.read_bytes()
    official_registry_path.write_bytes(official_registry_bytes)
    official_entries = require_official_registry_entries(
        load_model_registry_bytes(official_registry_bytes).entries
    )
    evaluation_models = registry_record(official_entries)
    release_anchor = earliest_eligible_decision_date(official_entries).isoformat()

    supplementary_registry_path = root / "supplementary-registry.json"
    supplementary_registry_path.write_bytes(
        sibling_registry_bytes
        if sibling_registry_bytes is not None
        else SUPPLEMENTARY_REGISTRY.read_bytes()
    )

    packets: list[dict[str, Any]] = []
    prompt_commitments: dict[str, str] = {}
    dates = decision_dates or [CORPUS_ANCHOR] * 100
    for index in range(100):
        candidate_id = f"candidate-{index:03d}"
        case_id = f"case-{index:03d}"
        for ablation in ("full_packet", "metadata_only"):
            payload = _json_bytes(
                {"ablation": ablation, "candidate_id": candidate_id, "case_id": case_id}
            )
            key = f"model-packets/{candidate_id}-{ablation}.json"
            packet_path = root / key
            packet_path.parent.mkdir(parents=True, exist_ok=True)
            packet_path.write_bytes(payload)
            row: dict[str, Any] = {
                "ablation": ablation,
                "candidate_id": candidate_id,
                "case_id": case_id,
                "packet_object_key": key,
                "packet_sha256": hashlib.sha256(payload).hexdigest(),
                "packet_size_bytes": len(payload),
            }
            if dates[index] is not None:
                row["decision_date"] = dates[index]
            packets.append(row)
            prompt_commitments[f"{candidate_id}:{ablation}"] = hashlib.sha256(
                f"{candidate_id}:{ablation}".encode()
            ).hexdigest()

    generated_at = "2026-08-26T12:00:00Z"
    signature = {
        "approval_line": (
            f"I approve corpus manifest {MANIFEST_DIGEST} as the frozen Cycle 1 "
            "forecast corpus."
        ),
        "bead_id": "legalforecastbench-fixture",
    }
    run_inputs_path = root / "run-inputs.json"
    run_input_bytes = _write_json(
        run_inputs_path,
        {
            "cycle_id": CYCLE_ID,
            "generated_at": generated_at,
            "model_packets": packets,
        },
    )
    run_record_bytes = _write_json(
        root / "manifest-mode-run-record.json",
        {
            "case_count": 100,
            "cycle_id": CYCLE_ID,
            "docket_tool_enabled": False,
            "entry_mode": "owner_signed_manifest",
            "evaluation_models": evaluation_models,
            "evaluation_release_anchor": release_anchor,
            "generated_at": generated_at,
            "manifest_sha256": MANIFEST_DIGEST,
            "owner_signature_reference": signature,
            "packet_ablations": ["full_packet", "metadata_only"],
            "packet_count": 200,
            "prompt_commitments": prompt_commitments,
            "provider_calls_made": 0,
            "required_eval_run_case_flags": ["--no-docket-tool"],
            "schema_version": str(MANIFEST_MODE_FORECAST_RUN_RECORD_V1),
        },
    )
    prompt_path = root / "prompt-contract.json"
    _write_json(
        prompt_path,
        {
            "artifact_role": "prompt",
            "cycle_id": CYCLE_ID,
            "prompt_replay": {
                "candidate_count": 100,
                "evaluation_models": evaluation_models,
                "evaluation_release_anchor": release_anchor,
                "manifest_sha256": MANIFEST_DIGEST,
                "model_registry_sha256": hashlib.sha256(
                    official_registry_bytes
                ).hexdigest(),
                "owner_manifest_bytes_sha256": hashlib.sha256(
                    manifest_bytes
                ).hexdigest(),
                "owner_signature_reference": signature,
                "packet_count": 200,
                "prompt_commitments": prompt_commitments,
                "run_inputs_sha256": hashlib.sha256(run_input_bytes).hexdigest(),
                "run_record_sha256": hashlib.sha256(run_record_bytes).hexdigest(),
            },
            "required_eval_run_case_flags": ["--no-docket-tool"],
            "schema_version": str(MANIFEST_FREEZE_RUNTIME_CONTRACT_V1),
            "use_docket_tool": False,
        },
    )

    shared: dict[FrozenArtifactName, Path] = {}
    sibling_shared: dict[FrozenArtifactName, Path] = {}
    for name in (
        FrozenArtifactName.UNITS,
        FrozenArtifactName.LABELS,
        FrozenArtifactName.SCORER,
        FrozenArtifactName.HARNESS,
        FrozenArtifactName.BASELINES,
        FrozenArtifactName.EXCLUSION_LEDGER,
        FrozenArtifactName.LABELING_POLICY,
        FrozenArtifactName.COHORT_POLICY,
    ):
        path = root / f"{name.value}.json"
        path.write_bytes(_json_bytes({"artifact": name.value}))
        shared[name] = path
        sibling_shared[name] = path
    if drift_shared_artifact:
        drifted = root / "drifted-harness.json"
        drifted.write_bytes(_json_bytes({"artifact": "harness", "drift": True}))
        sibling_shared[FrozenArtifactName.HARNESS] = drifted

    official_caps = root / "official-caps.json"
    official_caps.write_bytes(_json_bytes({"caps": "official"}))
    official_policy = root / "official-policy.json"
    official_policy.write_bytes(_json_bytes({"policy": "official"}))
    supplementary_caps = root / "supplementary-caps.json"
    supplementary_caps.write_bytes(_json_bytes({"caps": "supplementary"}))
    supplementary_policy = root / "supplementary-policy.json"
    supplementary_policy.write_bytes(_json_bytes({"policy": "supplementary"}))

    official_freeze = root / "official.freeze.json"
    official_bundle = _freeze(
        official_freeze,
        registry_path=official_registry_path,
        prompt_path=prompt_path,
        manifest_path=manifest_path,
        shared=shared,
        caps_path=official_caps,
        policy_path=official_policy,
    )
    sibling_freeze = root / "sibling.freeze.json"
    sibling_bundle = _freeze(
        sibling_freeze,
        registry_path=supplementary_registry_path,
        prompt_path=prompt_path,
        manifest_path=manifest_path,
        shared=sibling_shared,
        caps_path=supplementary_caps,
        policy_path=supplementary_policy,
    )

    bundles = {official_freeze: official_bundle, sibling_freeze: sibling_bundle}

    def _verify(path: Any, **_kwargs: Any) -> FreezeBundle:
        # Stubs only the policy-artifact validation, which needs a full set of
        # real Cycle 1 policy documents and is not what these tests exercise.
        return bundles[Path(path)]

    monkeypatch.setattr(auth_module, "verify_freeze_bundle", _verify)
    monkeypatch.setattr(
        auth_module,
        "load_signed_manifest_bytes",
        lambda *_a, **_k: SimpleNamespace(
            cycle_id=CYCLE_ID,
            cases=tuple(
                SimpleNamespace(
                    candidate_id=f"candidate-{index:03d}",
                    case_id=f"case-{index:03d}",
                )
                for index in range(100)
            ),
        ),
    )
    return _Chain(
        root=root,
        official_freeze=official_freeze,
        sibling_freeze=sibling_freeze,
        official_registry=official_registry_path,
        supplementary_registry=supplementary_registry_path,
        run_inputs=run_inputs_path,
    )


def _request(
    chain: _Chain,
    *,
    supplementary: bool,
    freeze_bundle: Path | None = None,
    model_keys: tuple[str, ...] | None = None,
    output_name: str = "receipt.json",
) -> ManifestCostProjectionRequest:
    return ManifestCostProjectionRequest(
        freeze_bundle=freeze_bundle
        or (chain.sibling_freeze if supplementary else chain.official_freeze),
        freeze_root=chain.root,
        manifest_run_root=chain.root,
        amendment_bundles=(),
        cycle_id=CYCLE_ID,
        model_keys=model_keys
        or ((SUPPLEMENTARY_MODEL_KEY,) if supplementary else (OFFICIAL_MODEL_KEY,)),
        ablations=("full_packet", "metadata_only"),
        repeat_count=1,
        repeat_sample_case_ids=(),
        max_projected_model_cost_usd=None,
        matrix_limit=800,
        shard_only=False,
        output=chain.root / output_name,
        supplementary=supplementary,
        official_freeze_bundle=chain.official_freeze if supplementary else None,
    )


# --- The gap itself -------------------------------------------------------


def test_supplementary_projection_records_both_bindings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chain = _chain(tmp_path, monkeypatch)

    receipt = issue_manifest_cost_projection(_chain_request(chain))

    binding = receipt["supplementary_binding"]
    assert binding["execution_mode"] == "supplementary_post_anchor"
    assert binding["supplementary_model_keys"] == [SUPPLEMENTARY_MODEL_KEY]
    assert binding["corpus_anchor"] == CORPUS_ANCHOR
    assert binding["official_evaluation_release_anchor"] == "2026-06-26"
    # Both bindings are recorded, not inferable: the official contract this run
    # reuses and the registry it actually evaluates.
    assert binding["official_model_registry_sha256"] == (
        hashlib.sha256(OFFICIAL_REGISTRY.read_bytes()).hexdigest()
    )
    assert binding["supplementary_model_registry_sha256"] == (
        hashlib.sha256(SUPPLEMENTARY_REGISTRY.read_bytes()).hexdigest()
    )
    assert binding["official_freeze_bundle_sha256"] == (
        hashlib.sha256(chain.official_freeze.read_bytes()).hexdigest()
    )


def _chain_request(chain: _Chain) -> ManifestCostProjectionRequest:
    return _request(chain, supplementary=True)


def test_official_projection_receipt_keys_are_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The official four's receipt bytes must not move; their chain is live.

    Pinned against the field set the projector had before this lane existed, so
    an accidentally always-on field fails here rather than silently invalidating
    every already-issued official scope.
    """

    from legalforecast.evals.corpus_manifest.cost_projector import (
        _COST_RECEIPT_FIELDS,
        _SUPPLEMENTARY_COST_RECEIPT_FIELDS,
    )

    chain = _chain(tmp_path, monkeypatch)

    receipt = issue_manifest_cost_projection(_request(chain, supplementary=False))

    assert set(receipt) == set(_COST_RECEIPT_FIELDS)
    assert _SUPPLEMENTARY_COST_RECEIPT_FIELDS - _COST_RECEIPT_FIELDS == {
        "supplementary_binding"
    }


# --- Both-direction refusals in the cost chain ----------------------------


def test_official_mode_refuses_the_sibling_freeze(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The journaled production failure, preserved exactly."""

    chain = _chain(tmp_path, monkeypatch)
    request = _request(
        chain,
        supplementary=False,
        freeze_bundle=chain.sibling_freeze,
        model_keys=(SUPPLEMENTARY_MODEL_KEY,),
    )

    with pytest.raises(
        ManifestCostProjectionError,
        match="model registry differs from frozen prompt replay commitment",
    ):
        issue_manifest_cost_projection(request)


def test_supplementary_mode_refuses_the_official_freeze(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chain = _chain(tmp_path, monkeypatch)
    request = _request(
        chain,
        supplementary=True,
        freeze_bundle=chain.official_freeze,
        model_keys=(OFFICIAL_MODEL_KEY,),
    )

    with pytest.raises(
        ManifestCostProjectionError,
        match="requires a model registry distinct from the official frozen registry",
    ):
        issue_manifest_cost_projection(request)


def test_supplementary_mode_refuses_a_registry_that_classifies_official(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mirrors the aggregate gate: the caller picks the lane, not the class."""

    official_entries = json.loads(OFFICIAL_REGISTRY.read_text())
    chain = _chain(
        tmp_path,
        monkeypatch,
        # Distinct bytes, so freeze identity passes; still pre-anchor models, so
        # the classification gate is what refuses.
        sibling_registry_bytes=_json_bytes(official_entries[:2]),
    )
    request = _request(chain, supplementary=True, model_keys=("openai:gpt-5.6-sol",))

    with pytest.raises(
        ManifestCostProjectionError,
        match="refuses models released on or before the corpus anchor",
    ):
        issue_manifest_cost_projection(request)


def test_supplementary_mode_refuses_a_drifted_shared_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Comparability is verified, not waived: shared bytes must be identical."""

    chain = _chain(tmp_path, monkeypatch, drift_shared_artifact=True)

    with pytest.raises(
        ManifestCostProjectionError,
        match="must reuse the official frozen bytes",
    ):
        issue_manifest_cost_projection(_chain_request(chain))


def test_supplementary_mode_refuses_an_undated_corpus(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chain = _chain(tmp_path, monkeypatch, decision_dates=[None] * 100)  # type: ignore[list-item]

    with pytest.raises(
        ManifestCostProjectionError,
        match="requires run-input decision dates to derive the corpus anchor",
    ):
        issue_manifest_cost_projection(_chain_request(chain))


def test_supplementary_mode_refuses_a_partially_dated_corpus(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dates: list[Any] = [CORPUS_ANCHOR] * 100
    dates[7] = None
    chain = _chain(tmp_path, monkeypatch, decision_dates=dates)

    with pytest.raises(
        ManifestCostProjectionError,
        match="cannot be derived from a partial set",
    ):
        issue_manifest_cost_projection(_chain_request(chain))


def test_request_requires_the_official_freeze_in_supplementary_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chain = _chain(tmp_path, monkeypatch)

    with pytest.raises(
        ManifestCostProjectionError, match="requires --official-freeze-bundle"
    ):
        replace(_request(chain, supplementary=True), official_freeze_bundle=None)


def test_request_refuses_the_official_freeze_in_official_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chain = _chain(tmp_path, monkeypatch)

    with pytest.raises(
        ManifestCostProjectionError, match="does not accept --official-freeze-bundle"
    ):
        replace(
            _request(chain, supplementary=False),
            official_freeze_bundle=chain.official_freeze,
        )


# --- The workflow-environment entry point, where the gap actually bit -----


def _workflow_environment(
    chain: _Chain, tmp_path: Path, **overrides: str
) -> dict[str, str]:
    environment = {
        "ABLATIONS": "full_packet,metadata_only",
        "COST_PROJECTION_RECEIPT_PATH": str(tmp_path / "workflow-receipt.json"),
        "CYCLE_ID": CYCLE_ID,
        "FREEZE_BUNDLE_PATH": str(chain.sibling_freeze),
        "FREEZE_ROOT": str(chain.root),
        "GITHUB_OUTPUT": str(tmp_path / "github-output"),
        "GITHUB_STEP_SUMMARY": str(tmp_path / "github-step-summary"),
        "MANIFEST_RUN_ROOT": str(chain.root),
        "MATRIX_LIMIT": "800",
        "MODEL_KEYS": SUPPLEMENTARY_MODEL_KEY,
        "OFFICIAL_FREEZE_BUNDLE_PATH": str(chain.official_freeze),
        "REPEAT_COUNT": "1",
        "SHARD_ONLY": "false",
        "SUPPLEMENTARY": "true",
    }
    environment.update(overrides)
    return environment


def test_workflow_environment_projector_accepts_supplementary_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The Actions "Build matrix JSON" step, which has no dry_run gate.

    Fixing the CLI alone would still have failed here: this entry point builds
    the matrix for every dispatch, paid or not.
    """

    chain = _chain(tmp_path, monkeypatch)

    receipt = issue_manifest_cost_projection_from_workflow_environment(
        _workflow_environment(chain, tmp_path)
    )

    assert receipt["supplementary_binding"]["execution_mode"] == (
        "supplementary_post_anchor"
    )


def test_workflow_environment_defaults_to_official_when_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fail closed by omission: no variable means the official lane."""

    chain = _chain(tmp_path, monkeypatch)
    environment = _workflow_environment(
        chain,
        tmp_path,
        FREEZE_BUNDLE_PATH=str(chain.official_freeze),
        MODEL_KEYS=OFFICIAL_MODEL_KEY,
    )
    del environment["SUPPLEMENTARY"]
    del environment["OFFICIAL_FREEZE_BUNDLE_PATH"]

    receipt = issue_manifest_cost_projection_from_workflow_environment(environment)

    assert "supplementary_binding" not in receipt


def test_workflow_environment_refuses_supplementary_without_official_freeze(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chain = _chain(tmp_path, monkeypatch)
    environment = _workflow_environment(chain, tmp_path, OFFICIAL_FREEZE_BUNDLE_PATH="")

    with pytest.raises(
        ManifestCostProjectionError, match="OFFICIAL_FREEZE_BUNDLE_PATH is required"
    ):
        issue_manifest_cost_projection_from_workflow_environment(environment)


def test_workflow_environment_refuses_official_freeze_in_official_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chain = _chain(tmp_path, monkeypatch)
    environment = _workflow_environment(chain, tmp_path, SUPPLEMENTARY="false")

    with pytest.raises(
        ManifestCostProjectionError,
        match="OFFICIAL_FREEZE_BUNDLE_PATH is only valid",
    ):
        issue_manifest_cost_projection_from_workflow_environment(environment)


# --- Execution scope: mode is bound into the artifact ---------------------


def _owner_observation(model_key: str, *, ceiling: str, estimate: str) -> bytes:
    return json.dumps(
        [
            {
                "author": "John Hughes",
                "created_at": "2026-08-29T12:00:00+00:00",
                "id": "comment-1",
                "issue_id": "legalforecastbench-fixture",
                "text": (
                    f"I approve up to USD {ceiling} of provider spend for model "
                    f"{model_key} in the Cycle 1 forecast run, estimated USD "
                    f"{estimate}."
                ),
            }
        ]
    ).encode()


def _scope(
    chain: _Chain, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Issue a real supplementary scope over a real supplementary receipt."""

    receipt = issue_manifest_cost_projection(_chain_request(chain))
    plan = issue_execution_plan_v4(
        cycle_id=CYCLE_ID,
        model_registry=chain.supplementary_registry,
        common_frozen_inputs={
            "manifest_sha256": hashlib.sha256(
                chain.root.joinpath("owner-manifest.json").read_bytes()
            ).hexdigest(),
            "run_input_manifest_sha256": hashlib.sha256(
                chain.run_inputs.read_bytes()
            ).hexdigest(),
            "model_registry_sha256": hashlib.sha256(
                chain.supplementary_registry.read_bytes()
            ).hexdigest(),
            "run_card_sha256": "c" * 64,
        },
    )
    projected = float(cast(str, receipt["projected_model_cost_usd"]))
    ceiling = f"{projected * 2:.2f}"
    observation = _owner_observation(
        SUPPLEMENTARY_MODEL_KEY, ceiling=ceiling, estimate=ceiling
    )
    monkeypatch.setattr(
        "legalforecast.evals.corpus_manifest.execution_decisions.capture_beads_comments",
        lambda _bead: {
            "raw_observation_base64": base64.b64encode(observation).decode("ascii"),
            "raw_observation_sha256": hashlib.sha256(observation).hexdigest(),
            **_parsed(observation),
        },
    )
    authority = {
        "backend": "dynamodb",
        "resource_identity_sha256": "d" * 64,
        "provider": "google",
        "account": "cycle1-google",
        "cap_microusd": int(projected * 2_000_000) + 1_000_000,
    }
    scope = issue_model_execution_scope(
        common_plan=plan,
        model_registry=chain.supplementary_registry,
        model_key=SUPPLEMENTARY_MODEL_KEY,
        cost_projection=receipt,
        run_input_manifest=chain.run_inputs,
        owner_ceiling_usd=ceiling,
        owner_bead_id="legalforecastbench-fixture",
        provider_authority=authority,
        supplementary=True,
    )
    return scope, plan, receipt


def _parsed(observation: bytes) -> dict[str, Any]:
    from legalforecast.evals.corpus_manifest.execution_scope import (
        _parse_owner_observation,
    )

    return dict(_parse_owner_observation(observation))


def test_supplementary_scope_records_the_binding_and_verifies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chain = _chain(tmp_path, monkeypatch)

    scope, plan, receipt = _scope(chain, tmp_path, monkeypatch)

    assert scope["scope"]["supplementary_binding"] == receipt["supplementary_binding"]
    verify_execution_scope(
        scope,
        common_plan=plan,
        model_registry=chain.supplementary_registry,
        cost_projection=receipt,
        run_input_manifest=chain.run_inputs,
        provider_authority=cast(dict[str, Any], scope["scope"])["provider_authority"],
        expected_model_key=SUPPLEMENTARY_MODEL_KEY,
        expected_supplementary=True,
    )


def test_supplementary_scope_cannot_authorize_an_official_shard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The default at consumption is official, so an unchanged caller refuses."""

    chain = _chain(tmp_path, monkeypatch)
    scope, plan, _receipt = _scope(chain, tmp_path, monkeypatch)
    registry = load_model_registry(chain.supplementary_registry)

    with pytest.raises(
        ExecutionScopeError,
        match="was issued in supplementary mode and cannot authorize an official",
    ):
        verify_execution_scope_runtime(
            scope,
            common_plan=plan,
            model_registry=registry,
            model_registry_sha256=hashlib.sha256(
                chain.supplementary_registry.read_bytes()
            ).hexdigest(),
            expected_model_key=SUPPLEMENTARY_MODEL_KEY,
            expected_ablation="full_packet",
        )


def test_supplementary_scope_is_accepted_by_a_supplementary_shard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chain = _chain(tmp_path, monkeypatch)
    scope, plan, _receipt = _scope(chain, tmp_path, monkeypatch)
    registry = load_model_registry(chain.supplementary_registry)

    assert (
        verify_execution_scope_runtime(
            scope,
            common_plan=plan,
            model_registry=registry,
            model_registry_sha256=hashlib.sha256(
                chain.supplementary_registry.read_bytes()
            ).hexdigest(),
            expected_model_key=SUPPLEMENTARY_MODEL_KEY,
            expected_ablation="full_packet",
            expected_supplementary=True,
        )
        == scope["scope_sha256"]
    )


def test_official_scope_cannot_authorize_a_supplementary_shard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chain = _chain(tmp_path, monkeypatch)
    scope, plan, _receipt = _scope(chain, tmp_path, monkeypatch)
    official_shape = {
        "schema_version": scope["schema_version"],
        "scope": {
            key: value
            for key, value in cast(dict[str, Any], scope["scope"]).items()
            if key != "supplementary_binding"
        },
    }
    from legalforecast.protocol.manifest import hash_payload

    official_shape["scope_sha256"] = hash_payload(official_shape["scope"])
    registry = load_model_registry(chain.supplementary_registry)

    with pytest.raises(
        ExecutionScopeError,
        match="was issued in official mode and cannot authorize a supplementary",
    ):
        verify_execution_scope_runtime(
            official_shape,
            common_plan=plan,
            model_registry=registry,
            model_registry_sha256=hashlib.sha256(
                chain.supplementary_registry.read_bytes()
            ).hexdigest(),
            expected_model_key=SUPPLEMENTARY_MODEL_KEY,
            expected_ablation="full_packet",
            expected_supplementary=True,
        )


# --- The workflow wiring the Python tests cannot reach --------------------


def test_workflow_threads_supplementary_into_the_matrix_and_scope_steps() -> None:
    """Pin the wiring the runner cannot see: the step env and the verifier call.

    The "Build matrix JSON" step has no ``dry_run`` gate, so it runs on every
    dispatch.  Fixing the CLI alone would have left the Actions path failing in
    exactly the place this bead was filed about.
    """

    workflow = (ROOT / ".github" / "workflows" / "run-benchmark.yaml").read_text()

    assert "SUPPLEMENTARY: ${{ inputs.supplementary }}" in workflow
    assert (
        "OFFICIAL_FREEZE_BUNDLE_PATH: ${{ inputs.supplementary && "
        "'/tmp/lfb-official-freeze.json' || '' }}"
    ) in workflow
    assert 'expected_supplementary=os.environ["SUPPLEMENTARY"] == "true",' in workflow
    # Both directions at dispatch validation, mirroring the library refusal.
    assert (
        "official_freeze_bundle_uri is required for a supplementary dispatch."
        in workflow
    )
    assert (
        "official_freeze_bundle_uri is only valid for a supplementary dispatch."
        in workflow
    )


def test_corpus_anchor_is_the_earliest_scored_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Derived from the corpus, never from the registry under evaluation."""

    dates = [CORPUS_ANCHOR] + ["2026-07-15"] * 99
    chain = _chain(tmp_path, monkeypatch, decision_dates=dates)

    receipt = issue_manifest_cost_projection(_chain_request(chain))

    assert receipt["supplementary_binding"]["corpus_anchor"] == CORPUS_ANCHOR
    assert date.fromisoformat(CORPUS_ANCHOR) < date(2026, 8, 13)
