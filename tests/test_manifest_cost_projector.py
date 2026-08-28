from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from legalforecast.contracts.schemas import (
    MANIFEST_FREEZE_RUNTIME_CONTRACT_V1,
    MANIFEST_MODE_FORECAST_RUN_RECORD_V1,
)
from legalforecast.evals.corpus_manifest import (
    cost_projector as projector_module,
)
from legalforecast.evals.corpus_manifest import (
    cost_projector_auth as auth_module,
)
from legalforecast.evals.corpus_manifest import (
    cost_projector_io as io_module,
)
from legalforecast.evals.corpus_manifest import (
    cost_projector_workflow as workflow_module,
)
from legalforecast.evals.corpus_manifest.cost_projector import (
    PROVIDER_LANES,
    ManifestCostProjectionError,
    ManifestCostProjectionRequest,
    _enforce_dispatch_ceiling,
    build_manifest_cost_projection,
    issue_manifest_cost_projection,
)
from legalforecast.evals.corpus_manifest.cost_projector_auth import (
    AuthenticatedManifestCostInputs,
    authenticate_manifest_cost_inputs,
)
from legalforecast.evals.corpus_manifest.cost_projector_workflow import (
    issue_manifest_cost_projection_from_workflow_environment,
)
from legalforecast.evals.corpus_manifest.records import registry_record
from legalforecast.evals.model_registry import (
    earliest_eligible_decision_date,
    load_model_registry_bytes,
    require_official_registry_entries,
)
from legalforecast.protocol.freeze import (
    FreezeBundle,
    FrozenArtifact,
    FrozenArtifactName,
)
from legalforecast.protocol.manifest import hash_payload

ROOT = Path(__file__).resolve().parents[1]
SUCCESSOR_REGISTRY = (
    ROOT
    / "model_registries"
    / "cycle-1-2026-06-30-claude-opus-4-8-successor-2026-08-21.json"
)
SUCCESSOR_MODEL_KEYS = (
    "openai:gpt-5.6-sol",
    "openai:gpt-5.6-terra",
    "openai:gpt-5.6-luna",
    "anthropic:claude-opus-4-8",
)
OFFICIAL_PACKET_ABLATIONS = ("full_packet", "metadata_only")


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _write_json(path: Path, value: object) -> bytes:
    payload = _json_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return payload


def _packet_payload(candidate_id: str, case_id: str, ablation: str) -> bytes:
    return _json_bytes(
        {
            "ablation": ablation,
            "candidate_id": candidate_id,
            "case_id": case_id,
        }
    )


def _packet_row(
    case_id: str,
    *,
    ablation: str = "full_packet",
    input_tokens: int | None = 100,
    candidate_id: str | None = None,
    payload: bytes | None = None,
) -> tuple[dict[str, Any], bytes]:
    candidate = candidate_id or case_id
    packet_payload = payload or _packet_payload(candidate, case_id, ablation)
    key = f"model-packets/{candidate}-{ablation}.json"
    row: dict[str, Any] = {
        "ablation": ablation,
        "candidate_id": candidate,
        "case_id": case_id,
        "packet_object_key": key,
        "packet_sha256": hashlib.sha256(packet_payload).hexdigest(),
        "packet_size_bytes": len(packet_payload),
    }
    if input_tokens is not None:
        row["estimated_input_tokens"] = input_tokens
    return row, packet_payload


def _simple_registry() -> list[dict[str, Any]]:
    return [
        {
            "input_token_price": 2.0,
            "max_output_tokens": 50,
            "model_id": "model-a",
            "output_token_price": 4.0,
            "provider": "anthropic",
        },
        {
            "input_token_price": 1.0,
            "max_output_tokens": 25,
            "model_id": "model-b",
            "output_token_price": 2.0,
            "provider": "gemini",
        },
    ]


def _request(
    tmp_path: Path,
    *,
    model_keys: tuple[str, ...] = ("anthropic:model-a",),
    ablations: tuple[str, ...] = ("full_packet",),
    repeat_count: int = 1,
    repeat_sample_case_ids: tuple[str, ...] = (),
    max_projected_model_cost_usd: str | None = None,
    matrix_limit: int = 256,
    shard_only: bool = True,
) -> ManifestCostProjectionRequest:
    tmp_path.mkdir(parents=True, exist_ok=True)
    return ManifestCostProjectionRequest(
        freeze_bundle=tmp_path / "freeze.json",
        freeze_root=tmp_path,
        manifest_run_root=tmp_path,
        amendment_bundles=(),
        cycle_id="cycle-1",
        model_keys=model_keys,
        ablations=ablations,
        repeat_count=repeat_count,
        repeat_sample_case_ids=repeat_sample_case_ids,
        max_projected_model_cost_usd=max_projected_model_cost_usd,
        matrix_limit=matrix_limit,
        shard_only=shard_only,
        output=tmp_path / "cost-projection.json",
    )


def _authenticated(
    rows: list[tuple[dict[str, Any], bytes]],
    *,
    registry: list[dict[str, Any]] | None = None,
    snapshots: dict[Path, bytes] | None = None,
) -> AuthenticatedManifestCostInputs:
    packets = [row for row, _payload in rows]
    packet_payloads = {
        cast(str, row["packet_object_key"]): payload for row, payload in rows
    }
    registry_records = registry or _simple_registry()
    return AuthenticatedManifestCostInputs(
        run_inputs={"cycle_id": "cycle-1", "model_packets": packets},
        registry_records=registry_records,
        run_input_bytes=b"run-inputs\n",
        registry_bytes=_json_bytes(registry_records),
        packet_payloads=packet_payloads,
        snapshots=snapshots or {},
        input_commitments={"fixture": {"sha256": "0" * 64, "size_bytes": 0}},
    )


def _build(
    tmp_path: Path,
    rows: list[tuple[dict[str, Any], bytes]],
    *,
    registry: list[dict[str, Any]] | None = None,
    **request_overrides: object,
) -> dict[str, Any]:
    request = _request(tmp_path, **request_overrides)
    return build_manifest_cost_projection(
        request, authenticated=_authenticated(rows, registry=registry)
    )


def _issued(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    rows: list[tuple[dict[str, Any], bytes]],
    *,
    registry: list[dict[str, Any]] | None = None,
    snapshots: dict[Path, bytes] | None = None,
    **request_overrides: object,
) -> tuple[ManifestCostProjectionRequest, dict[str, Any]]:
    request = _request(tmp_path, **request_overrides)
    authenticated = _authenticated(rows, registry=registry, snapshots=snapshots)
    monkeypatch.setattr(
        projector_module,
        "authenticate_manifest_cost_inputs",
        lambda _request: authenticated,
    )
    return request, issue_manifest_cost_projection(request)


@pytest.mark.parametrize(
    "token_field",
    [
        "estimated_input_tokens",
        "input_tokens",
        "prompt_tokens",
        "estimated_prompt_tokens",
        "packet_token_count",
        "token_count",
    ],
)
def test_projector_preserves_authenticated_token_fallback_order(
    tmp_path: Path, token_field: str
) -> None:
    row, payload = _packet_row("case-1", input_tokens=None)
    row[token_field] = 250
    row["token_count"] = 999_999

    receipt = _build(tmp_path, [(row, payload)])

    expected = "2.000198" if token_field == "token_count" else "0.000700"
    assert receipt["projected_model_cost_usd"] == expected


def test_projector_packet_size_fallback_uses_authenticated_byte_length(
    tmp_path: Path,
) -> None:
    payload = b"x" * 1_001
    row, _ = _packet_row("case-bytes", input_tokens=None, payload=payload)

    receipt = _build(tmp_path, [(row, payload)])

    assert receipt["projected_model_cost_usd"] == "0.000702"


def test_projector_preserves_terra_binary_float_rounding(tmp_path: Path) -> None:
    terra = [
        {
            "input_token_price": 2.5,
            "max_output_tokens": 16_000,
            "model_id": "gpt-5.6-terra",
            "output_token_price": 15.0,
            "provider": "openai",
        }
    ]

    receipt = _build(
        tmp_path,
        [_packet_row("case-1", input_tokens=35_259)],
        registry=terra,
        model_keys=("openai:gpt-5.6-terra",),
    )

    assert receipt["projected_model_cost_usd"] == "0.328147"
    assert receipt["recommended_max_projected_model_cost_usd"] == "0.656295"


@pytest.mark.parametrize(
    ("ceiling", "message"),
    [
        ("0.3281475", None),
        ("0.328147", "exceeds budget"),
        ("0.656295", None),
        ("0.656296", "exceeds the 2x"),
    ],
)
def test_projector_preserves_exact_binary_float_ceiling_boundaries(
    tmp_path: Path, ceiling: str, message: str | None
) -> None:
    terra = [
        {
            "input_token_price": 2.5,
            "max_output_tokens": 16_000,
            "model_id": "gpt-5.6-terra",
            "output_token_price": 15.0,
            "provider": "openai",
        }
    ]
    arguments = {
        "registry": terra,
        "model_keys": ("openai:gpt-5.6-terra",),
        "max_projected_model_cost_usd": ceiling,
    }
    if message is None:
        receipt = _build(
            tmp_path, [_packet_row("case-1", input_tokens=35_259)], **arguments
        )
        assert receipt["max_projected_model_cost_usd"] == ceiling
        return

    with pytest.raises(ManifestCostProjectionError, match=message):
        _build(tmp_path, [_packet_row("case-1", input_tokens=35_259)], **arguments)


def test_enforce_dispatch_ceiling_accepts_advertised_2x_despite_binary_float() -> None:
    projected = 79.6700003
    recommended = projected * 2
    advertised = f"{recommended:.6f}"
    assert float(advertised) > recommended
    _enforce_dispatch_ceiling(
        projected_cost=projected,
        recommended_ceiling=recommended,
        requested_raw=advertised,
    )
    with pytest.raises(ManifestCostProjectionError, match="exceeds the 2x"):
        _enforce_dispatch_ceiling(
            projected_cost=projected,
            recommended_ceiling=recommended,
            requested_raw=f"{float(advertised) + 1e-6:.6f}",
        )


def test_projector_accepts_its_own_recommended_live_cap(tmp_path: Path) -> None:
    terra = [
        {
            "input_token_price": 2.5,
            "max_output_tokens": 16_000,
            "model_id": "gpt-5.6-terra",
            "output_token_price": 15.0,
            "provider": "openai",
        }
    ]
    packets = [_packet_row("case-1", input_tokens=35_259)]
    dry = _build(
        tmp_path / "dry",
        packets,
        registry=terra,
        model_keys=("openai:gpt-5.6-terra",),
    )
    recommended = dry["recommended_max_projected_model_cost_usd"]
    live = _build(
        tmp_path / "live",
        packets,
        registry=terra,
        model_keys=("openai:gpt-5.6-terra",),
        max_projected_model_cost_usd=recommended,
    )
    assert live["max_projected_model_cost_usd"] == recommended


def test_projector_multiplies_repeat_cost_and_partitions_provider_matrices(
    tmp_path: Path,
) -> None:
    receipt = _build(
        tmp_path,
        [
            _packet_row("case-repeat", input_tokens=1_000),
            _packet_row("case-once"),
        ],
        model_keys=("anthropic:model-a", "gemini:model-b"),
        repeat_count=3,
        repeat_sample_case_ids=("case-repeat",),
        matrix_limit=800,
        shard_only=False,
    )

    assert receipt["projected_model_cost_usd"] == "0.010300"
    assert receipt["provider_counts"] == {
        "anthropic": 2,
        "gemini": 2,
        "openai": 0,
    }
    assert receipt["case_count"] == 2
    assert receipt["packet_count"] == 2
    assert receipt["cell_count"] == 2
    assert receipt["matrix_row_count"] == 4
    assert receipt["shard_matrix_row_count"] == 2
    assert receipt["request_count"] == 4
    assert receipt["attempt_count"] == 8
    assert receipt["model_count"] == 2
    assert {row["repeat_count"] for row in receipt["matrix"]["include"]} == {1, 3}


@pytest.mark.parametrize(("tokens", "warning_count"), [(272_000, 0), (272_001, 1)])
def test_projector_preserves_long_context_warning_boundary(
    tmp_path: Path, tokens: int, warning_count: int
) -> None:
    receipt = _build(tmp_path, [_packet_row("case-long", input_tokens=tokens)])

    assert receipt["long_context_surcharge_packet_count"] == warning_count
    assert len(receipt["long_context_surcharge_packets"]) == warning_count


def test_projector_applies_terra_long_context_surcharge_strictly_after_boundary(
    tmp_path: Path,
) -> None:
    terra = [
        {
            "input_token_price": 2.5,
            "max_output_tokens": 16_000,
            "model_id": "gpt-5.6-terra",
            "output_token_price": 15.0,
            "provider": "gemini",
            "long_context_surcharge": {
                "input_price_multiplier": 2.0,
                "output_price_multiplier": 1.5,
                "threshold_input_tokens": 272_000,
            },
        }
    ]

    at_boundary = _build(
        tmp_path / "at-boundary",
        [_packet_row("case-long", input_tokens=272_000)],
        registry=terra,
        model_keys=("gemini:gpt-5.6-terra",),
    )
    over_boundary = _build(
        tmp_path / "over-boundary",
        [_packet_row("case-long", input_tokens=272_001)],
        registry=terra,
        model_keys=("gemini:gpt-5.6-terra",),
    )

    assert at_boundary["projected_model_cost_usd"] == "0.920000"
    assert over_boundary["projected_model_cost_usd"] == "1.720005"


def test_projector_does_not_surcharge_registry_without_long_context_term(
    tmp_path: Path,
) -> None:
    receipt = _build(
        tmp_path,
        [_packet_row("case-long", input_tokens=272_001)],
        model_keys=("anthropic:model-a",),
    )

    assert receipt["projected_model_cost_usd"] == "0.544202"


def test_projector_receipt_has_canonical_self_hash(tmp_path: Path) -> None:
    receipt = _build(tmp_path, [_packet_row("case-1")])

    body = dict(receipt)
    claimed = body.pop("receipt_sha256")
    assert claimed == hash_payload(body)


def test_projector_publishes_exact_canonical_receipt_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request, receipt = _issued(tmp_path, monkeypatch, [_packet_row("case-1")])

    assert request.output.read_bytes() == (
        json.dumps(
            receipt,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        + b"\n"
    )


def test_input_drift_before_install_leaves_no_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.json"
    source.write_bytes(b"changed")
    request = _request(tmp_path)
    authenticated = _authenticated(
        [_packet_row("case-1")], snapshots={source: b"original"}
    )
    monkeypatch.setattr(
        projector_module,
        "authenticate_manifest_cost_inputs",
        lambda _request: authenticated,
    )

    with pytest.raises(ManifestCostProjectionError, match="input changed"):
        issue_manifest_cost_projection(request)

    assert not request.output.exists()


def test_source_mutation_after_final_prelink_recheck_rolls_back_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.json"
    source.write_bytes(b"original")
    request = _request(tmp_path)
    authenticated = _authenticated(
        [_packet_row("case-1")], snapshots={source: b"original"}
    )
    monkeypatch.setattr(
        projector_module,
        "authenticate_manifest_cost_inputs",
        lambda _request: authenticated,
    )
    original_link = io_module.os.link

    def racing_link(*args: object, **kwargs: object) -> None:
        source.write_bytes(b"changed-after-prelink-recheck")
        original_link(*args, **kwargs)

    monkeypatch.setattr(io_module.os, "link", racing_link)

    with pytest.raises(ManifestCostProjectionError, match="input changed"):
        issue_manifest_cost_projection(request)

    assert not request.output.exists()
    assert list(tmp_path.glob(".*.partial")) == []


def test_staged_write_failure_leaves_no_final_or_partial_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = _request(tmp_path)
    monkeypatch.setattr(
        projector_module,
        "authenticate_manifest_cost_inputs",
        lambda _request: _authenticated([_packet_row("case-1")]),
    )
    monkeypatch.setattr(io_module.os, "write", lambda *_args, **_kwargs: _raise_os())

    with pytest.raises(ManifestCostProjectionError, match="cannot create"):
        issue_manifest_cost_projection(request)

    assert not request.output.exists()
    assert list(tmp_path.glob("*.partial")) == []
    assert list(tmp_path.glob(".*.partial")) == []


def _raise_os() -> int:
    raise OSError("injected staged write failure")


def test_post_commit_cleanup_failure_does_not_report_failed_issuance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = _request(tmp_path)
    monkeypatch.setattr(
        projector_module,
        "authenticate_manifest_cost_inputs",
        lambda _request: _authenticated([_packet_row("case-1")]),
    )
    original_link = io_module.os.link
    original_close = io_module.os.close
    committed = False
    injected = False

    def tracking_link(*args: object, **kwargs: object) -> None:
        nonlocal committed
        original_link(*args, **kwargs)
        committed = True

    def flaky_close(descriptor: int) -> None:
        nonlocal injected
        original_close(descriptor)
        if committed and not injected:
            injected = True
            raise OSError("injected post-commit close failure")

    monkeypatch.setattr(io_module.os, "link", tracking_link)
    monkeypatch.setattr(io_module.os, "close", flaky_close)

    receipt = issue_manifest_cost_projection(request)

    assert injected
    assert json.loads(request.output.read_bytes()) == receipt


def test_destination_race_preserves_competitor_without_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = _request(tmp_path)
    monkeypatch.setattr(
        projector_module,
        "authenticate_manifest_cost_inputs",
        lambda _request: _authenticated([_packet_row("case-1")]),
    )
    original_link = io_module.os.link

    def racing_link(*args: object, **kwargs: object) -> None:
        request.output.write_bytes(b"competitor")
        original_link(*args, **kwargs)

    monkeypatch.setattr(io_module.os, "link", racing_link)

    with pytest.raises(ManifestCostProjectionError, match="appeared concurrently"):
        issue_manifest_cost_projection(request)

    assert request.output.read_bytes() == b"competitor"
    assert list(tmp_path.glob(".*.partial")) == []


def test_symlinked_output_ancestor_never_writes_through_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_parent = tmp_path / "real"
    real_parent.mkdir()
    linked_parent = tmp_path / "linked"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    request = replace(
        _request(tmp_path / "request"), output=linked_parent / "receipt.json"
    )
    monkeypatch.setattr(
        projector_module,
        "authenticate_manifest_cost_inputs",
        lambda _request: _authenticated([_packet_row("case-1")]),
    )

    with pytest.raises(ManifestCostProjectionError, match="parent is unsafe"):
        issue_manifest_cost_projection(request)

    assert not (real_parent / "receipt.json").exists()


def test_output_parent_swap_after_link_unlinks_from_pinned_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_parent = tmp_path / "requested-parent"
    output_parent.mkdir()
    detached_parent = tmp_path / "detached-parent"
    request = replace(
        _request(tmp_path / "request"), output=output_parent / "receipt.json"
    )
    monkeypatch.setattr(
        projector_module,
        "authenticate_manifest_cost_inputs",
        lambda _request: _authenticated([_packet_row("case-1")]),
    )
    original_link = io_module.os.link

    def racing_link(*args: object, **kwargs: object) -> None:
        original_link(*args, **kwargs)
        output_parent.rename(detached_parent)
        output_parent.mkdir()

    monkeypatch.setattr(io_module.os, "link", racing_link)

    with pytest.raises(ManifestCostProjectionError, match="output parent changed"):
        issue_manifest_cost_projection(request)

    assert not request.output.exists()
    assert not (detached_parent / request.output.name).exists()
    assert list(detached_parent.glob(".*.partial")) == []


def _authenticated_chain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    packet_ablations: tuple[str, str] = OFFICIAL_PACKET_ABLATIONS,
    packet_identity_mode: str = "signed",
    packet_input_tokens: int | None = 100,
) -> tuple[ManifestCostProjectionRequest, list[Path]]:
    root = tmp_path / "freeze-root"
    root.mkdir()
    manifest_bytes = b'{"cycle_id":"cycle-1"}\n'
    manifest_path = root / "owner-manifest.json"
    manifest_path.write_bytes(manifest_bytes)
    manifest_digest = "a" * 64

    registry_bytes = SUCCESSOR_REGISTRY.read_bytes()
    registry_path = root / "registry.json"
    registry_path.write_bytes(registry_bytes)
    entries = require_official_registry_entries(
        load_model_registry_bytes(registry_bytes).entries
    )
    evaluation_models = registry_record(entries)
    release_anchor = earliest_eligible_decision_date(entries).isoformat()

    packets: list[dict[str, Any]] = []
    packet_paths: list[Path] = []
    prompt_commitments: dict[str, str] = {}
    for index in range(100):
        if packet_identity_mode == "foreign":
            candidate_id = f"foreign-candidate-{index:03d}"
            case_id = f"foreign-case-{index:03d}"
        else:
            candidate_id = f"candidate-{index:03d}"
            case_index = (
                (index + 1) % 100 if packet_identity_mode == "mismatch" else index
            )
            case_id = f"case-{case_index:03d}"
        for ablation in packet_ablations:
            row, payload = _packet_row(
                case_id,
                ablation=ablation,
                candidate_id=candidate_id,
                input_tokens=packet_input_tokens,
            )
            packet_path = root / cast(str, row["packet_object_key"])
            packet_path.parent.mkdir(parents=True, exist_ok=True)
            packet_path.write_bytes(payload)
            packet_paths.append(packet_path)
            packets.append(row)
            prompt_commitments[f"{candidate_id}:{ablation}"] = hashlib.sha256(
                f"{candidate_id}:{ablation}".encode()
            ).hexdigest()

    generated_at = "2026-08-22T12:00:00Z"
    signature = {
        "approval_line": (
            f"I approve corpus manifest {manifest_digest} as the frozen Cycle 1 "
            "forecast corpus."
        ),
        "bead_id": "legalforecastbench-fixture",
    }
    run_inputs = {
        "cycle_id": "cycle-1",
        "generated_at": generated_at,
        "model_packets": packets,
    }
    run_input_bytes = _write_json(root / "run-inputs.json", run_inputs)
    run_record = {
        "case_count": 100,
        "cycle_id": "cycle-1",
        "docket_tool_enabled": False,
        "entry_mode": "owner_signed_manifest",
        "evaluation_models": evaluation_models,
        "evaluation_release_anchor": release_anchor,
        "generated_at": generated_at,
        "manifest_sha256": manifest_digest,
        "owner_signature_reference": signature,
        "packet_ablations": ["full_packet", "metadata_only"],
        "packet_count": 200,
        "prompt_commitments": prompt_commitments,
        "provider_calls_made": 0,
        "required_eval_run_case_flags": ["--no-docket-tool"],
        "schema_version": str(MANIFEST_MODE_FORECAST_RUN_RECORD_V1),
    }
    run_record_bytes = _write_json(root / "manifest-mode-run-record.json", run_record)
    prompt_replay = {
        "candidate_count": 100,
        "evaluation_models": evaluation_models,
        "evaluation_release_anchor": release_anchor,
        "manifest_sha256": manifest_digest,
        "model_registry_sha256": hashlib.sha256(registry_bytes).hexdigest(),
        "owner_manifest_bytes_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "owner_signature_reference": signature,
        "packet_count": 200,
        "prompt_commitments": prompt_commitments,
        "run_inputs_sha256": hashlib.sha256(run_input_bytes).hexdigest(),
        "run_record_sha256": hashlib.sha256(run_record_bytes).hexdigest(),
    }
    prompt_bytes = _write_json(
        root / "prompt-contract.json",
        {
            "artifact_role": "prompt",
            "cycle_id": "cycle-1",
            "prompt_replay": prompt_replay,
            "required_eval_run_case_flags": ["--no-docket-tool"],
            "schema_version": str(MANIFEST_FREEZE_RUNTIME_CONTRACT_V1),
            "use_docket_tool": False,
        },
    )

    selected_payloads = {
        FrozenArtifactName.MANIFEST: (manifest_path, manifest_bytes),
        FrozenArtifactName.MODEL_REGISTRY: (registry_path, registry_bytes),
        FrozenArtifactName.PROMPT: (root / "prompt-contract.json", prompt_bytes),
    }
    artifacts: list[FrozenArtifact] = []
    for artifact_name in FrozenArtifactName:
        path, payload = selected_payloads.get(
            artifact_name,
            (root / f"{artifact_name.value}.json", b"{}\n"),
        )
        if not path.exists():
            path.write_bytes(payload)
        artifacts.append(
            FrozenArtifact(
                name=artifact_name,
                path=path,
                sha256=hashlib.sha256(payload).hexdigest(),
                size_bytes=len(payload),
            )
        )
    bundle = FreezeBundle(
        cycle_id="cycle-1",
        freeze_timestamp=datetime(2026, 8, 22, tzinfo=UTC),
        artifacts=tuple(artifacts),
    )
    freeze_path = root / "freeze.json"
    freeze_path.write_bytes(b"{}\n")
    monkeypatch.setattr(auth_module, "verify_freeze_bundle", lambda *_a, **_k: bundle)
    monkeypatch.setattr(
        auth_module,
        "load_signed_manifest_bytes",
        lambda *_a, **_k: SimpleNamespace(
            cycle_id="cycle-1",
            cases=tuple(
                SimpleNamespace(
                    candidate_id=f"candidate-{index:03d}",
                    case_id=f"case-{index:03d}",
                )
                for index in range(100)
            ),
        ),
    )
    return (
        ManifestCostProjectionRequest(
            freeze_bundle=freeze_path,
            freeze_root=root,
            manifest_run_root=root,
            amendment_bundles=(),
            cycle_id="cycle-1",
            model_keys=("openai:gpt-5.6-terra",),
            ablations=("full_packet", "metadata_only"),
            repeat_count=1,
            repeat_sample_case_ids=(),
            max_projected_model_cost_usd=None,
            matrix_limit=800,
            shard_only=False,
            output=root / "receipt.json",
        ),
        packet_paths,
    )


def test_complete_frozen_manifest_chain_authenticates_every_packet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request, _packet_paths = _authenticated_chain(tmp_path, monkeypatch)

    authenticated = authenticate_manifest_cost_inputs(request)

    assert len(authenticated.packet_payloads) == 200
    assert len(authenticated.input_commitments["packets"]) == 200
    assert authenticated.input_commitments["model_registry"]["sha256"] == (
        hashlib.sha256(SUCCESSOR_REGISTRY.read_bytes()).hexdigest()
    )


def test_cost_verifier_recomputes_authenticated_numeric_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request, _packet_paths = _authenticated_chain(
        tmp_path, monkeypatch, packet_input_tokens=None
    )
    authenticated = authenticate_manifest_cost_inputs(request)
    receipt = build_manifest_cost_projection(request, authenticated=authenticated)
    registry_entry = next(
        entry
        for entry in load_model_registry_bytes(SUCCESSOR_REGISTRY.read_bytes()).entries
        if entry.registry_key == "openai:gpt-5.6-terra"
    )
    commitments = cast(dict[str, Any], receipt["input_commitments"])
    expected_common = {
        "freeze_bundle_sha256": commitments["freeze_bundle"]["sha256"],
        "manifest_sha256": commitments["owner_manifest"]["sha256"],
        "run_input_manifest_sha256": commitments["run_input_manifest"]["sha256"],
        "model_registry_sha256": commitments["model_registry"]["sha256"],
    }
    assert (
        projector_module.verify_manifest_cost_projection_receipt(
            receipt,
            expected_cycle_id="cycle-1",
            expected_model_key="openai:gpt-5.6-terra",
            expected_common_frozen_inputs=expected_common,
            expected_registry_entry=registry_entry.to_record(),
            run_input_manifest=authenticated.run_input_bytes,
        )
        == receipt["receipt_sha256"]
    )

    tampered = dict(receipt)
    tampered["projected_model_cost_usd"] = "0.000001"
    tampered["receipt_sha256"] = hash_payload(
        {key: value for key, value in tampered.items() if key != "receipt_sha256"}
    )
    with pytest.raises(
        ManifestCostProjectionError, match="authenticated pricing projection"
    ):
        projector_module.verify_manifest_cost_projection_receipt(
            tampered,
            expected_cycle_id="cycle-1",
            expected_model_key="openai:gpt-5.6-terra",
            expected_common_frozen_inputs=expected_common,
            expected_registry_entry=registry_entry.to_record(),
            run_input_manifest=authenticated.run_input_bytes,
        )


def test_scope_mode_rejects_legacy_cost_packet_commitments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request, _packet_paths = _authenticated_chain(
        tmp_path, monkeypatch, packet_input_tokens=None
    )
    authenticated = authenticate_manifest_cost_inputs(request)
    receipt = build_manifest_cost_projection(request, authenticated=authenticated)
    commitments = cast(dict[str, Any], receipt["input_commitments"])
    legacy_receipt = json.loads(json.dumps(receipt))
    legacy_commitments = cast(dict[str, Any], legacy_receipt["input_commitments"])
    for packet in cast(list[dict[str, Any]], legacy_commitments["packets"]):
        packet.pop("input_tokens")
    legacy_receipt["receipt_sha256"] = hash_payload(
        {key: value for key, value in legacy_receipt.items() if key != "receipt_sha256"}
    )
    registry_entry = next(
        entry
        for entry in load_model_registry_bytes(SUCCESSOR_REGISTRY.read_bytes()).entries
        if entry.registry_key == "openai:gpt-5.6-terra"
    )
    expected_common = {
        "freeze_bundle_sha256": commitments["freeze_bundle"]["sha256"],
        "manifest_sha256": commitments["owner_manifest"]["sha256"],
        "run_input_manifest_sha256": commitments["run_input_manifest"]["sha256"],
        "model_registry_sha256": commitments["model_registry"]["sha256"],
    }
    assert (
        projector_module.verify_manifest_cost_projection_receipt(
            legacy_receipt,
            expected_cycle_id="cycle-1",
            expected_model_key="openai:gpt-5.6-terra",
            expected_common_frozen_inputs=expected_common,
            expected_registry_entry=registry_entry.to_record(),
        )
        == legacy_receipt["receipt_sha256"]
    )
    for packet in cast(list[dict[str, Any]], commitments["packets"]):
        packet.pop("input_tokens")
    receipt["receipt_sha256"] = hash_payload(
        {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    )
    with pytest.raises(ManifestCostProjectionError, match="input_tokens"):
        projector_module.verify_manifest_cost_projection_receipt(
            receipt,
            expected_cycle_id="cycle-1",
            expected_model_key="openai:gpt-5.6-terra",
            expected_common_frozen_inputs=expected_common,
            expected_registry_entry=registry_entry.to_record(),
            run_input_manifest=authenticated.run_input_bytes,
        )


def test_authenticated_packet_matrix_rejects_unexpected_ablation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request, _packet_paths = _authenticated_chain(
        tmp_path,
        monkeypatch,
        packet_ablations=("full_packet", "unexpected"),
    )

    with pytest.raises(ManifestCostProjectionError, match="exact 100x2 packet matrix"):
        authenticate_manifest_cost_inputs(request)


@pytest.mark.parametrize("packet_identity_mode", ["foreign", "mismatch"])
def test_authenticated_packet_matrix_requires_signed_manifest_case_mapping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    packet_identity_mode: str,
) -> None:
    request, _packet_paths = _authenticated_chain(
        tmp_path, monkeypatch, packet_identity_mode=packet_identity_mode
    )

    with pytest.raises(ManifestCostProjectionError, match="signed owner manifest"):
        authenticate_manifest_cost_inputs(request)


def test_aggregate_projection_has_eight_cells_and_800_requests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request, _packet_paths = _authenticated_chain(tmp_path, monkeypatch)
    authenticated = authenticate_manifest_cost_inputs(request)

    receipt = build_manifest_cost_projection(
        replace(
            request,
            model_keys=SUCCESSOR_MODEL_KEYS,
            ablations=OFFICIAL_PACKET_ABLATIONS,
            matrix_limit=800,
            shard_only=False,
        ),
        authenticated=authenticated,
    )

    assert receipt["case_count"] == 100
    assert receipt["packet_count"] == 200
    assert receipt["cell_count"] == 8
    assert receipt["matrix_row_count"] == 800
    assert receipt["shard_matrix_row_count"] == 100
    assert receipt["request_count"] == 800
    assert len(receipt["matrix"]["include"]) == 800


@pytest.mark.parametrize(
    ("model_key", "ablation"),
    [
        (model_key, ablation)
        for model_key in SUCCESSOR_MODEL_KEYS
        for ablation in OFFICIAL_PACKET_ABLATIONS
    ],
)
def test_each_official_shard_has_exactly_100_matrix_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    model_key: str,
    ablation: str,
) -> None:
    request, _packet_paths = _authenticated_chain(tmp_path, monkeypatch)
    authenticated = authenticate_manifest_cost_inputs(request)

    receipt = build_manifest_cost_projection(
        replace(
            request,
            model_keys=(model_key,),
            ablations=(ablation,),
            matrix_limit=256,
            shard_only=True,
        ),
        authenticated=authenticated,
    )

    assert receipt["case_count"] == 100
    assert receipt["packet_count"] == 200
    assert receipt["cell_count"] == 1
    assert receipt["matrix_row_count"] == 100
    assert receipt["shard_matrix_row_count"] == 100
    assert receipt["request_count"] == 100
    assert len(receipt["matrix"]["include"]) == 100


@pytest.mark.parametrize("mutation", ["missing", "substituted"])
def test_missing_or_substituted_packet_fails_authentication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    request, packet_paths = _authenticated_chain(tmp_path, monkeypatch)
    packet = packet_paths[0]
    if mutation == "missing":
        packet.unlink()
    else:
        payload = packet.read_bytes()
        packet.write_bytes(payload.replace(b"case-000", b"case-999"))

    with pytest.raises(ManifestCostProjectionError, match="packet"):
        authenticate_manifest_cost_inputs(request)


def test_hardlinked_authenticated_input_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request, _packet_paths = _authenticated_chain(tmp_path, monkeypatch)
    run_inputs = request.manifest_run_root / "run-inputs.json"
    os.link(run_inputs, request.manifest_run_root / "run-inputs-alias.json")

    with pytest.raises(ManifestCostProjectionError, match="must not be hardlinked"):
        authenticate_manifest_cost_inputs(request)


def test_symlinked_authenticated_input_ancestor_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request, _packet_paths = _authenticated_chain(tmp_path, monkeypatch)
    packet_root = request.manifest_run_root / "model-packets"
    real_packet_root = request.manifest_run_root / "real-model-packets"
    packet_root.rename(real_packet_root)
    packet_root.symlink_to(real_packet_root, target_is_directory=True)

    with pytest.raises(ManifestCostProjectionError, match="symlink"):
        authenticate_manifest_cost_inputs(request)


def test_cli_help_requires_authenticated_roots_and_omits_arbitrary_inputs() -> None:
    completed = subprocess.run(
        [
            str(Path(sys.executable).with_name("legalforecast")),
            "acquisition",
            "project-manifest-cost",
            "--help",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "--freeze-bundle" in completed.stdout
    assert "--freeze-root" in completed.stdout
    assert "--manifest-run-root" in completed.stdout
    assert "--amendment-bundle" in completed.stdout
    assert "--run-input-manifest" not in completed.stdout
    assert "--model-registry" not in completed.stdout


def test_workflow_adapter_uses_authenticated_manifest_root_and_emits_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[ManifestCostProjectionRequest] = []
    receipt: dict[str, Any] = {
        "shard_only": True,
        "matrix": {"include": []},
        "case_count": 100,
        "packet_count": 200,
        "cell_count": 1,
        "matrix_row_count": 100,
        "shard_matrix_row_count": 100,
        "request_count": 100,
        "attempt_count": 100,
        "model_count": 1,
        "long_context_surcharge_packet_count": 0,
        "long_context_surcharge_packets": [],
        "long_context_surcharge_packets_json": "[]",
        "projected_model_cost_usd": "0.328147",
        "recommended_max_projected_model_cost_usd": "0.656295",
    }
    for provider in ("openai", "anthropic", "gemini"):
        receipt[f"{provider}_count"] = 1 if provider == "openai" else 0
        receipt[f"{provider}_matrix"] = {"include": []}
    monkeypatch.setattr(
        workflow_module,
        "issue_manifest_cost_projection",
        lambda request: captured.append(request) or receipt,
    )
    github_output = tmp_path / "github-output"
    summary = tmp_path / "summary"
    root = tmp_path / "manifest-root"

    actual = issue_manifest_cost_projection_from_workflow_environment(
        {
            "ABLATIONS": "full_packet,metadata_only",
            "COST_PROJECTION_RECEIPT_PATH": str(tmp_path / "receipt.json"),
            "CYCLE_ID": "cycle-1",
            "FREEZE_AMENDMENT_BUNDLES": "a.freeze.json\nb.freeze.json\n",
            "FREEZE_BUNDLE_PATH": str(root / "freeze.json"),
            "FREEZE_ROOT": str(root),
            "GITHUB_OUTPUT": str(github_output),
            "GITHUB_STEP_SUMMARY": str(summary),
            "MANIFEST_RUN_ROOT": str(root),
            "MATRIX_LIMIT": "256",
            "MAX_PROJECTED_MODEL_COST_USD": "0.656295",
            "MODEL_KEYS": "openai:gpt-5.6-terra",
            "REPEAT_COUNT": "1",
            "REPEAT_SAMPLE_CASE_IDS": "",
            "SHARD_ONLY": "true",
        }
    )

    assert actual is receipt
    assert captured[0].freeze_bundle == root / "freeze.json"
    assert captured[0].manifest_run_root == root
    assert captured[0].amendment_bundles == (
        Path("a.freeze.json"),
        Path("b.freeze.json"),
    )
    assert "projected_model_cost_usd=0.328147\n" in github_output.read_text()
    assert "Projected model cost: $0.33" in summary.read_text()


def test_workflow_adapter_omits_matrix_rows_from_aggregate_github_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    huge_matrix = {"include": [{"case_id": f"case-{index}"} for index in range(800)]}
    receipt: dict[str, Any] = {
        "shard_only": False,
        "matrix": huge_matrix,
        "case_count": 100,
        "packet_count": 200,
        "cell_count": 8,
        "matrix_row_count": 800,
        "shard_matrix_row_count": 100,
        "request_count": 800,
        "attempt_count": 800,
        "model_count": 4,
        "long_context_surcharge_packet_count": 0,
        "long_context_surcharge_packets": [],
        "long_context_surcharge_packets_json": "[]",
        "projected_model_cost_usd": "40.510000",
        "recommended_max_projected_model_cost_usd": "81.020000",
    }
    for provider in PROVIDER_LANES:
        receipt[f"{provider}_count"] = 800 if provider == "openai" else 0
        receipt[f"{provider}_matrix"] = huge_matrix
    monkeypatch.setattr(
        workflow_module,
        "issue_manifest_cost_projection",
        lambda _request: receipt,
    )
    github_output = tmp_path / "github-output"
    summary = tmp_path / "summary"
    root = tmp_path / "manifest-root"

    issue_manifest_cost_projection_from_workflow_environment(
        {
            "ABLATIONS": "full_packet,metadata_only",
            "COST_PROJECTION_RECEIPT_PATH": str(tmp_path / "receipt.json"),
            "CYCLE_ID": "cycle-1",
            "FREEZE_AMENDMENT_BUNDLES": "",
            "FREEZE_BUNDLE_PATH": str(root / "freeze.json"),
            "FREEZE_ROOT": str(root),
            "GITHUB_OUTPUT": str(github_output),
            "GITHUB_STEP_SUMMARY": str(summary),
            "MANIFEST_RUN_ROOT": str(root),
            "MATRIX_LIMIT": "800",
            "MAX_PROJECTED_MODEL_COST_USD": "81.020000",
            "MODEL_KEYS": (
                "openai:gpt-5.6-sol,openai:gpt-5.6-terra,"
                "openai:gpt-5.6-luna,anthropic:claude-sonnet-5"
            ),
            "REPEAT_COUNT": "1",
            "REPEAT_SAMPLE_CASE_IDS": "",
            "SHARD_ONLY": "false",
        }
    )

    output = github_output.read_text()
    assert "matrix=" not in output
    assert "_matrix=" not in output
    assert "openai_count=800\n" in output
    assert "matrix_row_count=800\n" in output
    assert len(output) < 5000
