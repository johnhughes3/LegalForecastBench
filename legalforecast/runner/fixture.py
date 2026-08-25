"""Deterministic provider-free public-runner fixture issuer and transport."""

from __future__ import annotations

import json
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import cast
from urllib.request import Request

from legalforecast.contracts import ARTIFACT_CANONICAL_JSON_V1
from legalforecast.evals.model_registry import ModelRegistry
from legalforecast.immutable_io import publish_tree_create_only
from legalforecast.release import issue_synthetic_release

FIXTURE_MODEL_ID = "legalforecast-fixture"
FIXTURE_MODEL_VERSION = "legalforecast-fixture-2026-08-23"
FIXTURE_MODEL_KEY = f"openai:{FIXTURE_MODEL_ID}"

JsonRecord = Mapping[str, object]


class FixtureModelTransport:
    """OpenAI-shaped deterministic transport that performs no network I/O."""

    def __init__(self) -> None:
        self.call_count = 0

    def __call__(self, request: Request, timeout_seconds: float) -> JsonRecord:
        del timeout_seconds
        self.call_count += 1
        if request.data is None:
            raise ValueError("fixture provider request body is missing")
        request_bytes = cast(bytes, request.data)
        payload = cast(dict[str, object], json.loads(request_bytes))
        if payload.get("model") != FIXTURE_MODEL_ID:
            raise ValueError("fixture transport requires the frozen fixture model")
        prompt = payload.get("input")
        if not isinstance(prompt, str):
            raise ValueError("fixture provider prompt is missing")
        unit_id = _unit_id_from_prompt(prompt)
        probability = {
            "unit-001": 0.2,
            "unit-002": 0.8,
            "unit-003": 0.5,
        }[unit_id]
        output = json.dumps(
            {
                "case_assessment": "Deterministic provider-free fixture.",
                "predictions": [
                    {
                        "probability_fully_dismissed": probability,
                        "unit_id": unit_id,
                    }
                ],
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        return {
            "model": FIXTURE_MODEL_VERSION,
            "output_text": output,
            "service_tier": "flex",
            "status": "completed",
            "usage": {"input_tokens": 20, "output_tokens": 10},
        }


def issue_runner_fixture(output_dir: Path) -> None:
    """Create-only publish a release plus its runnable fixture registry."""

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="legalforecast-runner-fixture-",
        dir=output_dir.parent,
    ) as temporary:
        release_dir = Path(temporary) / "release"
        issue_synthetic_release(release_dir)
        payloads = {
            f"release/{path.relative_to(release_dir).as_posix()}": path.read_bytes()
            for path in release_dir.rglob("*")
            if path.is_file()
        }
        registry = ModelRegistry.from_records(
            [
                {
                    "provider": "openai",
                    "model_id": FIXTURE_MODEL_ID,
                    "display_name": "LegalForecast provider-free fixture",
                    "model_version_or_snapshot": FIXTURE_MODEL_VERSION,
                    "release_timestamp": "2026-08-23T00:00:00Z",
                    "release_timestamp_source": "repository fixture",
                    "provider_training_cutoff_status": "not_disclosed",
                    "provider_training_cutoff": None,
                    "max_output_tokens": 256,
                    "network_disabled": True,
                    "search_disabled": True,
                    "tool_policy": "no_tools",
                    "context_limit": 4096,
                    "pricing_source": "provider-free fixture",
                    "input_token_price": 1.0,
                    "output_token_price": 1.0,
                    "known_cutoff_publicity_caveats": [],
                }
            ]
        )
        payloads["model-registry.json"] = ARTIFACT_CANONICAL_JSON_V1.encode(
            registry.to_records()
        )
        publish_tree_create_only(output_dir, payloads)


def _unit_id_from_prompt(prompt: str) -> str:
    matches = tuple(
        unit_id for unit_id in ("unit-001", "unit-002", "unit-003") if unit_id in prompt
    )
    if len(matches) != 1:
        raise ValueError("fixture prompt must identify exactly one synthetic unit")
    return matches[0]
