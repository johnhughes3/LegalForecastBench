from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from legalforecast.evals.corpus_manifest import cost_projector as projector_module
from legalforecast.evals.corpus_manifest.cost_projector import (
    ManifestCostProjectionError,
    ManifestCostProjectionRequest,
    issue_manifest_cost_projection,
)
from legalforecast.evals.corpus_manifest.cost_projector_workflow import (
    issue_manifest_cost_projection_from_workflow_environment,
)

ROOT = Path(__file__).resolve().parents[1]


def _write_json(path: Path, value: object) -> bytes:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.write_bytes(payload)
    return payload


def _packet(
    case_id: str,
    *,
    ablation: str = "full_packet",
    input_tokens: int = 100,
) -> dict[str, Any]:
    return {
        "ablation": ablation,
        "case_id": case_id,
        "estimated_input_tokens": input_tokens,
        "packet_object_key": f"model-packets/{case_id}-{ablation}.json",
        "packet_sha256": hashlib.sha256(case_id.encode()).hexdigest(),
    }


def _registry() -> list[dict[str, Any]]:
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
    packets: list[dict[str, Any]] | None = None,
    model_keys: tuple[str, ...] = ("anthropic:model-a",),
    ablations: tuple[str, ...] = ("full_packet",),
    repeat_count: int = 1,
    repeat_sample_case_ids: tuple[str, ...] = (),
    max_projected_model_cost_usd: str | None = None,
) -> ManifestCostProjectionRequest:
    tmp_path.mkdir(parents=True, exist_ok=True)
    manifest = tmp_path / "run-inputs.json"
    registry = tmp_path / "registry.json"
    output = tmp_path / "cost-projection.json"
    _write_json(
        manifest,
        {
            "cycle_id": "cycle-1",
            "model_packets": packets or [_packet("case-1")],
        },
    )
    _write_json(registry, _registry())
    return ManifestCostProjectionRequest(
        run_input_manifest=manifest,
        model_registry=registry,
        cycle_id="cycle-1",
        model_keys=model_keys,
        ablations=ablations,
        repeat_count=repeat_count,
        repeat_sample_case_ids=repeat_sample_case_ids,
        max_projected_model_cost_usd=max_projected_model_cost_usd,
        matrix_limit=256,
        output=output,
    )


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ([], "run-input manifest must be a JSON object"),
        ({"cycle_id": "cycle-1"}, "model_packets list"),
        (
            {"cycle_id": "cycle-1", "model_packets": ["not-an-object"]},
            "model_packets entries must be objects",
        ),
    ],
)
def test_projector_refuses_malformed_manifest(
    tmp_path: Path, payload: object, message: str
) -> None:
    request = _request(tmp_path)
    _write_json(request.run_input_manifest, payload)

    with pytest.raises(ManifestCostProjectionError, match=message):
        issue_manifest_cost_projection(request)

    assert not request.output.exists()


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
def test_projector_preserves_packet_token_field_fallbacks(
    tmp_path: Path, token_field: str
) -> None:
    packet = _packet("case-1")
    packet.pop("estimated_input_tokens")
    packet[token_field] = 250
    request = _request(tmp_path, packets=[packet])

    receipt = issue_manifest_cost_projection(request)

    assert receipt["projected_model_cost_usd"] == "0.000700"


def test_projector_uses_first_valid_token_field_and_packet_size_fallback(
    tmp_path: Path,
) -> None:
    first = _packet("case-first", input_tokens=200)
    first["input_tokens"] = 999_999
    packet_size = _packet("case-bytes")
    packet_size.pop("estimated_input_tokens")
    packet_size["packet_size_bytes"] = 1_001
    request = _request(tmp_path, packets=[first, packet_size])

    receipt = issue_manifest_cost_projection(request)

    assert receipt["projected_model_cost_usd"] == "0.001302"


def test_projector_multiplies_repeat_cost_and_preserves_provider_matrices(
    tmp_path: Path,
) -> None:
    request = _request(
        tmp_path,
        packets=[_packet("case-repeat", input_tokens=1_000), _packet("case-once")],
        model_keys=("anthropic:model-a", "gemini:model-b"),
        repeat_count=3,
        repeat_sample_case_ids=("case-repeat",),
    )

    receipt = issue_manifest_cost_projection(request)

    assert receipt["projected_model_cost_usd"] == "0.010300"
    assert receipt["provider_counts"] == {
        "anthropic": 2,
        "gemini": 2,
        "openai": 0,
    }
    assert receipt["case_count"] == 2
    assert receipt["model_count"] == 2
    assert receipt["case_ids"] == ["case-repeat", "case-once"]
    assert receipt["repeat_sample_case_ids"] == ["case-repeat"]
    assert {row["repeat_count"] for row in receipt["matrix"]["include"]} == {1, 3}


def test_projector_consumes_the_committed_successor_registry(tmp_path: Path) -> None:
    request = _request(
        tmp_path,
        packets=[
            _packet("case-1", ablation="full_packet"),
            _packet("case-1", ablation="metadata_only"),
        ],
        model_keys=(
            "openai:gpt-5.6-sol",
            "openai:gpt-5.6-terra",
            "openai:gpt-5.6-luna",
            "anthropic:claude-opus-4-8",
        ),
        ablations=("full_packet", "metadata_only"),
    )
    request = replace(
        request,
        model_registry=(
            ROOT / "model_registries/"
            "cycle-1-2026-06-30-claude-opus-4-8-successor-2026-08-21.json"
        ),
    )

    receipt = issue_manifest_cost_projection(request)

    assert receipt["projected_model_cost_usd"] == "2.434700"
    assert receipt["provider_counts"] == {
        "anthropic": 2,
        "gemini": 0,
        "openai": 6,
    }


def test_projector_accepts_exact_cost_ceiling_and_refuses_one_micro_below(
    tmp_path: Path,
) -> None:
    exact = _request(
        tmp_path / "exact",
        packets=[_packet("case-1", input_tokens=400_000)],
        max_projected_model_cost_usd="0.8002000",
    )
    receipt = issue_manifest_cost_projection(exact)

    assert receipt["projected_model_cost_usd"] == "0.800200"
    assert receipt["max_projected_model_cost_usd"] == "0.8002000"

    below = _request(
        tmp_path / "below",
        packets=[_packet("case-1", input_tokens=400_000)],
        max_projected_model_cost_usd="0.800199",
    )
    with pytest.raises(ManifestCostProjectionError, match="exceeds budget"):
        issue_manifest_cost_projection(below)


def test_projector_refuses_ceiling_one_micro_over_early_warning_limit(
    tmp_path: Path,
) -> None:
    request = _request(
        tmp_path,
        packets=[_packet("case-1", input_tokens=400_000)],
        max_projected_model_cost_usd="1.600401",
    )

    with pytest.raises(ManifestCostProjectionError, match="exceeds the 2x"):
        issue_manifest_cost_projection(request)


def test_projector_records_long_context_warning_without_changing_formula(
    tmp_path: Path,
) -> None:
    packet = _packet("case-long", input_tokens=272_001)
    request = _request(tmp_path, packets=[packet])

    receipt = issue_manifest_cost_projection(request)

    assert receipt["projected_model_cost_usd"] == "0.544202"
    assert receipt["long_context_surcharge_packet_count"] == 1
    assert receipt["long_context_surcharge_packets"] == [
        {
            "ablation": "full_packet",
            "case_id": "case-long",
            "estimated_input_tokens": 272_001,
            "packet_object_key": "model-packets/case-long-full_packet.json",
            "packet_sha256": hashlib.sha256(b"case-long").hexdigest(),
        }
    ]


def test_projector_emits_canonical_receipt_with_raw_input_commitments(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path)
    manifest_bytes = request.run_input_manifest.read_bytes()
    registry_bytes = request.model_registry.read_bytes()

    receipt = issue_manifest_cost_projection(request)

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
    assert receipt["input_commitments"] == {
        "model_registry": {
            "sha256": hashlib.sha256(registry_bytes).hexdigest(),
            "size_bytes": len(registry_bytes),
        },
        "run_input_manifest": {
            "sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "size_bytes": len(manifest_bytes),
        },
    }


def test_projector_refuses_input_commitment_drift_before_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = _request(tmp_path)
    original_read = projector_module._read_regular
    manifest_reads = 0

    def drifting_read(path: Path, label: str) -> bytes:
        nonlocal manifest_reads
        payload = original_read(path, label)
        if path == request.run_input_manifest:
            manifest_reads += 1
            if manifest_reads == 2:
                return payload + b" "
        return payload

    monkeypatch.setattr(projector_module, "_read_regular", drifting_read)

    with pytest.raises(ManifestCostProjectionError, match="input changed"):
        issue_manifest_cost_projection(request)

    assert not request.output.exists()


def test_projector_is_available_as_supported_acquisition_command(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path)

    completed = subprocess.run(
        [
            str(Path(sys.executable).with_name("legalforecast")),
            "acquisition",
            "project-manifest-cost",
            "--run-input-manifest",
            str(request.run_input_manifest),
            "--model-registry",
            str(request.model_registry),
            "--cycle-id",
            request.cycle_id,
            "--model-key",
            "anthropic:model-a",
            "--ablation",
            "full_packet",
            "--repeat-count",
            "1",
            "--output",
            str(request.output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(request.output.read_bytes())["projected_model_cost_usd"] == (
        "0.000400"
    )


def test_workflow_adapter_emits_shared_matrices_outputs_and_summary(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path)
    github_output = tmp_path / "github-output"
    step_summary = tmp_path / "step-summary"

    receipt = issue_manifest_cost_projection_from_workflow_environment(
        {
            "ABLATIONS": "full_packet",
            "COST_PROJECTION_RECEIPT_PATH": str(request.output),
            "CYCLE_ID": request.cycle_id,
            "GITHUB_OUTPUT": str(github_output),
            "GITHUB_STEP_SUMMARY": str(step_summary),
            "MATRIX_LIMIT": "256",
            "MAX_PROJECTED_MODEL_COST_USD": "",
            "MODEL_KEYS": "anthropic:model-a",
            "MODEL_REGISTRY_PATH": str(request.model_registry),
            "REPEAT_COUNT": "1",
            "REPEAT_SAMPLE_CASE_IDS": "",
            "RUN_INPUT_MANIFEST_PATH": str(request.run_input_manifest),
        }
    )

    output = github_output.read_text(encoding="utf-8")
    assert f"matrix={json.dumps(receipt['matrix'], separators=(',', ':'))}\n" in output
    assert "anthropic_count=1\n" in output
    assert "projected_model_cost_usd=0.000400\n" in output
    summary = step_summary.read_text(encoding="utf-8")
    assert "Projected model cost: $0.00" in summary
    assert "early-warning control" in summary
