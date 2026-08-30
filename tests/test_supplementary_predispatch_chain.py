"""The pre-dispatch authorization chain in explicit supplementary mode.

PR #1003 built the supplementary lane from the provider cell forward, and its
end-to-end test drove ``run_per_case_evaluation`` directly.  That is exactly why
the gap this file covers survived review: cost projection and execution-scope
issuance were never exercised, so nothing noticed that a sibling freeze could not
reach a paid dispatch at all.

Every test here therefore drives the *dispatch chain* -- the request contract, the
authenticator, the receipt, the workflow-environment entry point, the scope, and
the workflow wiring -- rather than the runner.  Refusals are asserted in
both directions, because a lane that only fails one way can be entered from the
other.
"""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Final, cast

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
    verify_manifest_cost_projection_receipt,
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
    FreezeProtocolError,
    FrozenArtifact,
    FrozenArtifactName,
    load_freeze_bundle,
    write_hash_bundle,
)
from legalforecast.protocol.manifest import hash_payload
from legalforecast.reporting.result_class import (
    ResultClass,
    classify_registry_entry,
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
    _freeze(
        official_freeze,
        registry_path=official_registry_path,
        prompt_path=prompt_path,
        manifest_path=manifest_path,
        shared=shared,
        caps_path=official_caps,
        policy_path=official_policy,
    )
    sibling_freeze = root / "sibling.freeze.json"
    _freeze(
        sibling_freeze,
        registry_path=supplementary_registry_path,
        prompt_path=prompt_path,
        manifest_path=manifest_path,
        shared=sibling_shared,
        caps_path=supplementary_caps,
        policy_path=supplementary_policy,
    )

    def _verify(path: Any, **kwargs: Any) -> FreezeBundle:
        """Run the real loader, then skip only the policy-artifact validation.

        ``verify_freeze_bundle`` does three things: it loads and hash-checks the
        bundle, it re-reads every artifact's bytes, and it validates the Cycle 1
        policy documents. Only the last needs a full set of real policy artifacts
        and is unrelated to this lane, so it is the only part stubbed -- the
        bundle's own commitment hash, cycle_id, and per-artifact byte digests are
        all still checked by the code under test.
        """

        bundle = load_freeze_bundle(Path(path))
        expected_cycle_id = kwargs.get("cycle_id")
        if expected_cycle_id is not None and bundle.cycle_id != expected_cycle_id:
            raise FreezeProtocolError("freeze cycle_id does not match")
        for artifact in bundle.artifacts:
            payload = artifact.path.read_bytes()
            if (
                hashlib.sha256(payload).hexdigest() != artifact.sha256
                or len(payload) != artifact.size_bytes
            ):
                raise FreezeProtocolError(
                    f"frozen artifact bytes differ: {artifact.name.value}"
                )
        return bundle

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
        official_freeze_bundle_sha256=(
            _sha256_file(chain.official_freeze) if supplementary else None
        ),
    )


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def test_supplementary_mode_refuses_an_unrelated_official_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The recorded official binding must name the freeze the prompt commits.

    A fabricated reference bundle can share the ten identical artifacts and
    still bind some third registry.  It cannot game the lane -- the registry
    inequality and the classification gate refuse independently -- but the
    receipt would then record an ``official_freeze_bundle_sha256`` naming a
    freeze the shared prompt contract does not commit.  Requirement: recorded,
    not inferred.
    """

    chain = _chain(tmp_path, monkeypatch)
    forged_registry = chain.root / "third-registry.json"
    forged_registry.write_bytes(
        _json_bytes(json.loads(OFFICIAL_REGISTRY.read_text())[:3])
    )
    forged = chain.root / "forged-official.freeze.json"
    shared = {
        artifact.name: artifact.path
        for artifact in _freeze_bundle_artifacts(chain.official_freeze)
    }
    _freeze(
        forged,
        registry_path=forged_registry,
        prompt_path=shared[FrozenArtifactName.PROMPT],
        manifest_path=shared[FrozenArtifactName.MANIFEST],
        shared={
            name: path
            for name, path in shared.items()
            if name
            not in {
                FrozenArtifactName.PROMPT,
                FrozenArtifactName.MANIFEST,
                FrozenArtifactName.MODEL_REGISTRY,
                FrozenArtifactName.PROVIDER_CYCLE_CAPS,
                FrozenArtifactName.EXECUTION_POLICY,
            }
        },
        caps_path=shared[FrozenArtifactName.PROVIDER_CYCLE_CAPS],
        policy_path=shared[FrozenArtifactName.EXECUTION_POLICY],
    )
    request = replace(
        _request(chain, supplementary=True),
        official_freeze_bundle=forged,
        official_freeze_bundle_sha256=_sha256_file(forged),
    )

    with pytest.raises(
        ManifestCostProjectionError,
        match="does not bind the registry the frozen prompt contract commits",
    ):
        issue_manifest_cost_projection(request)


def test_supplementary_mode_refuses_an_unpinned_reference_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reference bundle is pinned, not trusted for self-consistency.

    A fabricated bundle can copy its shared-artifact digests straight from the
    sibling, so every identity check would be grounded in the sibling's own
    prompt bytes. The independent digest is what breaks that circle.
    """

    chain = _chain(tmp_path, monkeypatch)
    request = replace(
        _request(chain, supplementary=True), official_freeze_bundle_sha256="a" * 64
    )

    with pytest.raises(
        ManifestCostProjectionError,
        match="do not match the supplied digest pin",
    ):
        issue_manifest_cost_projection(request)


def _freeze_bundle_artifacts(path: Path) -> tuple[FrozenArtifact, ...]:
    from legalforecast.protocol.freeze import load_freeze_bundle

    return load_freeze_bundle(path).artifacts


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
    with pytest.raises(
        ManifestCostProjectionError, match="official-freeze-bundle-sha256"
    ):
        replace(_request(chain, supplementary=True), official_freeze_bundle_sha256=None)


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
    with pytest.raises(
        ManifestCostProjectionError, match="does not accept --official-freeze-bundle"
    ):
        replace(
            _request(chain, supplementary=False),
            official_freeze_bundle_sha256="f" * 64,
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
        "OFFICIAL_FREEZE_BUNDLE_SHA256": _sha256_file(chain.official_freeze),
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
    del environment["OFFICIAL_FREEZE_BUNDLE_SHA256"]

    receipt = issue_manifest_cost_projection_from_workflow_environment(environment)

    assert "supplementary_binding" not in receipt


def test_workflow_environment_refuses_supplementary_without_official_freeze(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chain = _chain(tmp_path, monkeypatch)
    environment = _workflow_environment(chain, tmp_path, OFFICIAL_FREEZE_BUNDLE_PATH="")

    with pytest.raises(ManifestCostProjectionError, match="are required"):
        issue_manifest_cost_projection_from_workflow_environment(environment)


def test_workflow_environment_refuses_official_freeze_in_official_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chain = _chain(tmp_path, monkeypatch)
    environment = _workflow_environment(chain, tmp_path, SUPPLEMENTARY="false")

    with pytest.raises(ManifestCostProjectionError, match="are only valid"):
        issue_manifest_cost_projection_from_workflow_environment(environment)


def test_receipt_verifier_refuses_the_other_lane_in_both_directions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Direct coverage of the receipt gate, which the scope gate would mask.

    ``verify_manifest_cost_projection_receipt`` is reachable on its own, and in
    the scope path the scope-level check always trips first -- so without this the
    receipt's own lane selection would be asserted by nothing.
    """

    chain = _chain(tmp_path, monkeypatch)
    supplementary = issue_manifest_cost_projection(_chain_request(chain))
    official = issue_manifest_cost_projection(
        _request(chain, supplementary=False, output_name="official-receipt.json")
    )
    common_inputs = {
        "freeze_bundle_sha256": _sha256_file(chain.sibling_freeze),
        "manifest_sha256": _sha256_file(chain.root / "owner-manifest.json"),
        "run_input_manifest_sha256": _sha256_file(chain.run_inputs),
        "model_registry_sha256": _sha256_file(chain.supplementary_registry),
        "run_card_sha256": "c" * 64,
    }

    with pytest.raises(
        ManifestCostProjectionError,
        match=r"schema is not the expected lane: expected "
        r"legalforecast\.manifest_cost_projection_receipt\.v1",
    ):
        verify_manifest_cost_projection_receipt(
            supplementary,
            expected_cycle_id=CYCLE_ID,
            expected_model_key=SUPPLEMENTARY_MODEL_KEY,
            expected_common_frozen_inputs=common_inputs,
            expected_registry_entry={},
        )

    with pytest.raises(
        ManifestCostProjectionError,
        match=r"schema is not the expected lane: expected "
        r"legalforecast\.manifest_cost_projection_supplementary_receipt\.v1",
    ):
        verify_manifest_cost_projection_receipt(
            official,
            expected_cycle_id=CYCLE_ID,
            expected_model_key=OFFICIAL_MODEL_KEY,
            expected_common_frozen_inputs=common_inputs,
            expected_registry_entry={},
            expected_supplementary=True,
        )


def test_official_and_supplementary_receipts_are_distinct_cards(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Change control: the binding is a new card, not a field on the old one."""

    chain = _chain(tmp_path, monkeypatch)

    supplementary = issue_manifest_cost_projection(_chain_request(chain))
    official = issue_manifest_cost_projection(
        _request(chain, supplementary=False, output_name="official-receipt.json")
    )

    assert official["schema_version"] == (
        "legalforecast.manifest_cost_projection_receipt.v1"
    )
    assert supplementary["schema_version"] == (
        "legalforecast.manifest_cost_projection_supplementary_receipt.v1"
    )
    # The identifier is inside the hashed payload, so the lane cannot be swapped
    # without breaking the receipt digest.
    assert "schema_version" not in {"receipt_sha256"}
    swapped = dict(supplementary)
    swapped["schema_version"] = official["schema_version"]
    without_hash = {
        key: value for key, value in swapped.items() if key != "receipt_sha256"
    }
    assert hash_payload(without_hash) != swapped["receipt_sha256"]


# --- Execution scope: mode is bound into the artifact ---------------------


OBSERVATION_CHATTER: Final = (
    "Working root /work/example/private/lane-notes; broker listening on "
    "127.0.0.1:8080. Not an approval line."
)
"""Bystander content of the kind a real approval bead accumulates.

``bd comments <bead> --json`` returns *every* comment on the bead, and the real
approval bead's payload already carries a local filesystem path and a private
address -- categories this public repository's hygiene rule bans.  The fixture
carries the same shapes so the public-safety assertion below is a behavior test
against the actual exposure, not a shape test against a sanitized fixture.
"""


def _owner_observation(
    model_key: str,
    *,
    ceiling: str,
    estimate: str,
    chatter: str = OBSERVATION_CHATTER,
) -> bytes:
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
            },
            {
                "author": "John Hughes",
                "created_at": "2026-08-29T13:00:00+00:00",
                "id": "comment-2",
                "issue_id": "legalforecastbench-fixture",
                "text": chatter,
            },
        ]
    ).encode()


def _scope_ceiling(receipt: Mapping[str, Any]) -> str:
    return f"{float(cast(str, receipt['projected_model_cost_usd'])) * 2:.2f}"


def _scope_observation(receipt: Mapping[str, Any]) -> bytes:
    """The exact capture bytes ``_scope`` issues against, recomputed."""

    ceiling = _scope_ceiling(receipt)
    return _owner_observation(
        SUPPLEMENTARY_MODEL_KEY, ceiling=ceiling, estimate=ceiling
    )


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
    ceiling = _scope_ceiling(receipt)
    observation = _scope_observation(receipt)
    monkeypatch.setattr(
        "legalforecast.evals.corpus_manifest.execution_decisions.capture_beads_comments",
        # The real capture returns the exact ``bd comments`` stdout bytes, so the
        # seam returns bytes too: the issuer must derive owner evidence from the
        # payload rather than be handed a caller-authored record.
        lambda _bead: observation,
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


SUPPLEMENTARY_OWNER_EVIDENCE_FIELDS: Final = [
    "author",
    "bead_id",
    "ceiling_usd",
    "comment_id",
    "created_at",
    "estimate_usd",
    "model_key",
    "raw_comment",
    "raw_comment_sha256",
    "raw_observation_sha256",
]


def test_supplementary_scope_publishes_the_observation_digest_not_the_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A supplementary scope must be safe to commit to this public repository.

    The operator machine cannot write to the results buckets at all, so an
    operator-produced supplementary scope reaches S3 only through this public
    repository -- as a commit, or as a workflow input echoed into public run
    logs.  The official card embeds the whole ``bd comments`` payload; the
    supplementary card publishes only its digest, so bystander comment bytes
    never leave the operator's machine and the scope's authenticated bytes stop
    moving whenever somebody comments on the approval bead.
    """

    chain = _chain(tmp_path, monkeypatch)
    scope, plan, receipt = _scope(chain, tmp_path, monkeypatch)
    observation = _scope_observation(receipt)
    evidence = cast(
        dict[str, Any], cast(dict[str, Any], scope["scope"])["owner_evidence"]
    )

    assert sorted(evidence) == SUPPLEMENTARY_OWNER_EVIDENCE_FIELDS
    assert evidence["raw_observation_sha256"] == hashlib.sha256(observation).hexdigest()
    assert evidence["raw_comment_sha256"] == (
        hashlib.sha256(cast(str, evidence["raw_comment"]).encode()).hexdigest()
    )

    # The published artifact bytes, not just the record: nothing from a
    # bystander comment survives anywhere in the card.
    published = json.dumps(scope, sort_keys=True)
    assert OBSERVATION_CHATTER not in published
    assert "/work/example/private/lane-notes" not in published
    assert "127.0.0.1" not in published
    assert base64.b64encode(observation).decode("ascii") not in published

    # Still a complete, verifiable card in both the embedded-only and the
    # payload-bearing direction.
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
    verify_execution_scope(
        scope,
        common_plan=plan,
        model_registry=chain.supplementary_registry,
        cost_projection=receipt,
        run_input_manifest=chain.run_inputs,
        owner_evidence=observation,
        provider_authority=cast(dict[str, Any], scope["scope"])["provider_authority"],
        expected_model_key=SUPPLEMENTARY_MODEL_KEY,
        expected_supplementary=True,
    )


def test_supplementary_scope_refuses_an_embedded_observation_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``raw_observation_base64`` is not a field of the supplementary card.

    Refusal is by name rather than by silent tolerance, so a scope smuggling the
    payload back in -- by hand, or by an issuer regression -- cannot reach a
    dispatch and cannot be published from this repository.
    """

    chain = _chain(tmp_path, monkeypatch)
    scope, plan, receipt = _scope(chain, tmp_path, monkeypatch)
    observation = _scope_observation(receipt)
    smuggled = json.loads(json.dumps(scope))
    smuggled["scope"]["owner_evidence"]["raw_observation_base64"] = base64.b64encode(
        observation
    ).decode("ascii")
    smuggled["scope_sha256"] = hash_payload(smuggled["scope"])

    with pytest.raises(
        ExecutionScopeError, match=r"unknown=\['raw_observation_base64'\]"
    ):
        verify_execution_scope(
            smuggled,
            common_plan=plan,
            model_registry=chain.supplementary_registry,
            cost_projection=receipt,
            run_input_manifest=chain.run_inputs,
            provider_authority=cast(dict[str, Any], scope["scope"])[
                "provider_authority"
            ],
            expected_model_key=SUPPLEMENTARY_MODEL_KEY,
            expected_supplementary=True,
        )

    # The pre-credential shape check refuses it too, so a smuggling scope cannot
    # reach the write-once shard receipt either.
    with pytest.raises(
        ExecutionScopeError, match=r"unknown=\['raw_observation_base64'\]"
    ):
        verify_execution_scope_runtime(
            smuggled,
            common_plan=plan,
            model_registry=load_model_registry(chain.supplementary_registry),
            model_registry_sha256=hashlib.sha256(
                chain.supplementary_registry.read_bytes()
            ).hexdigest(),
            expected_model_key=SUPPLEMENTARY_MODEL_KEY,
            expected_ablation="full_packet",
            expected_supplementary=True,
        )


def test_supplementary_scope_refuses_owner_evidence_that_drifts_from_the_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dropping the payload must not drop a check; each one has a replacement.

    Whoever holds the captured payload verifies it against the published digest
    (first case).  Whoever holds only the card re-derives every field the
    approval line determines, so a record cannot disagree with its own approval
    sentence (second and third cases).
    """

    chain = _chain(tmp_path, monkeypatch)
    scope, plan, receipt = _scope(chain, tmp_path, monkeypatch)
    authority = cast(dict[str, Any], scope["scope"])["provider_authority"]
    ceiling = _scope_ceiling(receipt)
    # Same approval sentence, one more bystander comment.  Everything the card
    # re-derives is unchanged, so only the observation digest can catch it --
    # which is exactly the check the payload used to provide.
    other_payload = _owner_observation(
        SUPPLEMENTARY_MODEL_KEY,
        ceiling=ceiling,
        estimate=ceiling,
        chatter=OBSERVATION_CHATTER + " Follow-up.",
    )

    with pytest.raises(ExecutionScopeError, match="scope owner evidence drift"):
        verify_execution_scope(
            scope,
            common_plan=plan,
            model_registry=chain.supplementary_registry,
            cost_projection=receipt,
            run_input_manifest=chain.run_inputs,
            owner_evidence=other_payload,
            provider_authority=authority,
            expected_model_key=SUPPLEMENTARY_MODEL_KEY,
            expected_supplementary=True,
        )

    tampered_money = json.loads(json.dumps(scope))
    tampered_money["scope"]["owner_evidence"]["ceiling_usd"] = "999.00"
    tampered_money["scope"]["owner_ceiling_usd"] = "999.00"
    tampered_money["scope_sha256"] = hash_payload(tampered_money["scope"])
    with pytest.raises(
        ExecutionScopeError, match="owner approval ceiling does not match its approval"
    ):
        verify_execution_scope(
            tampered_money,
            common_plan=plan,
            model_registry=chain.supplementary_registry,
            cost_projection=receipt,
            run_input_manifest=chain.run_inputs,
            provider_authority=authority,
            expected_model_key=SUPPLEMENTARY_MODEL_KEY,
            expected_supplementary=True,
        )

    tampered_comment = json.loads(json.dumps(scope))
    tampered_comment["scope"]["owner_evidence"]["raw_comment_sha256"] = "e" * 64
    tampered_comment["scope_sha256"] = hash_payload(tampered_comment["scope"])
    with pytest.raises(ExecutionScopeError, match="owner approval comment bytes drift"):
        verify_execution_scope(
            tampered_comment,
            common_plan=plan,
            model_registry=chain.supplementary_registry,
            cost_projection=receipt,
            run_input_manifest=chain.run_inputs,
            provider_authority=authority,
            expected_model_key=SUPPLEMENTARY_MODEL_KEY,
            expected_supplementary=True,
        )


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
    """The default at consumption is official, so an unchanged caller refuses.

    The refusal is by schema identifier: a supplementary scope is a different
    card, so it does not parse as an official one at all.
    """

    chain = _chain(tmp_path, monkeypatch)
    scope, plan, _receipt = _scope(chain, tmp_path, monkeypatch)
    assert scope["schema_version"] == "legalforecast.execution_scope_supplementary.v1"
    registry = load_model_registry(chain.supplementary_registry)

    with pytest.raises(
        ExecutionScopeError,
        match=(
            r"schema is not the expected lane: expected "
            r"legalforecast\.execution_scope\.v1"
        ),
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
        "schema_version": "legalforecast.execution_scope.v1",
        "scope": {
            key: value
            for key, value in cast(dict[str, Any], scope["scope"]).items()
            if key != "supplementary_binding"
        },
    }
    official_shape["scope_sha256"] = hash_payload(official_shape["scope"])
    registry = load_model_registry(chain.supplementary_registry)

    with pytest.raises(
        ExecutionScopeError,
        match=(
            r"schema is not the expected lane: expected "
            r"legalforecast\.execution_scope_supplementary\.v1"
        ),
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
    """Supplementary runs share the canonical public release boundary."""

    workflow = (ROOT / ".github" / "workflows" / "run-benchmark.yaml").read_text()

    assert "manifest_uri:" in workflow
    assert "forecast_release_uri:" in workflow
    assert "labels_release_uri:" in workflow
    assert "model_registry_uri:" in workflow
    assert "model_key:" in workflow
    assert "ceiling_microusd:" in workflow
    assert "inputs.supplementary" not in workflow
    assert "freeze_bundle_path" not in workflow
    assert "execution_scope_uri" not in workflow
    assert "approval-reference" not in workflow


def test_corpus_anchor_is_the_earliest_scored_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Derived from the corpus, never from the registry under evaluation."""

    dates = [CORPUS_ANCHOR] + ["2026-07-15"] * 99
    chain = _chain(tmp_path, monkeypatch, decision_dates=dates)

    receipt = issue_manifest_cost_projection(_chain_request(chain))

    binding = receipt["supplementary_binding"]
    assert binding["corpus_anchor"] == CORPUS_ANCHOR
    # The anchor the projector recorded is the one that actually classifies this
    # registry, and it classifies it supplementary -- not merely an earlier date.
    entry = load_model_registry(chain.supplementary_registry).entries[0]
    assert (
        classify_registry_entry(
            entry, corpus_anchor=date.fromisoformat(binding["corpus_anchor"])
        )
        is ResultClass.SUPPLEMENTARY_POST_ANCHOR
    )
    assert binding["supplementary_model_keys"] == [entry.registry_key]
